"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  FileText,
  GraduationCap,
  Loader2,
  Mail,
  Save,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Textarea } from "@/components/ui/textarea";
import {
  saveTranslationToNotebook,
  translateDocument,
  translateFromNotebook,
  translateImage,
  translateText,
  translateVideo,
} from "@/lib/api/translator";
import { getWrongQuestion, listWrongQuestions } from "@/lib/api/wrong-questions";
import type {
  TranslationResult,
  VideoTranslationResult,
  WrongQuestion,
} from "@/lib/api/types";
import { resolveUploadUrl } from "@/lib/config/api";
import { cn } from "@/lib/utils";
import { TranslationLoadingOverlay } from "@/components/translator/translation-loading-overlay";
import {
  formatTranslationResult,
  formatVideoCueText,
  formatVideoResultText,
  type TranslateDisplayMode,
} from "@/lib/translator/format-result";
import { CorrectedBilingualPanel } from "@/components/en-learn/corrected-bilingual-panel";
import { TtsReadAloudBar } from "@/components/en-learn/tts-read-aloud-bar";
import { WordLearningProvider } from "@/components/en-learn/word-learning-layer";
import { useTtsPlayback } from "@/hooks/use-tts-playback";
import {
  emailTranslationExport,
  getUserSettings,
  type ExportFormat,
} from "@/lib/api/settings";
import {
  enLearnTranslateImage,
  enLearnTranslateText,
  type EnLearnTranslateResult,
} from "@/lib/api/en-learn";

type SourceTab = "text" | "upload" | "notebook";
type TranslateMode = TranslateDisplayMode;
type UploadKind = "image" | "document" | "video";

type NotebookContentItem =
  | { kind: "notes"; label: string; text: string }
  | { kind: "file"; label: string; questionId: number; fileType: string };

function splitNoteBlocks(notes: string): string[] {
  const trimmed = notes.trim();
  if (!trimmed) return [];
  const blocks = trimmed
    .split(/\n{2,}/)
    .map((b) => b.trim())
    .filter(Boolean);
  return blocks.length > 0 ? blocks : [trimmed];
}

function detectUploadKind(file: File): UploadKind | null {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (["png", "jpg", "jpeg", "webp", "gif"].includes(ext)) return "image";
  if (["pdf", "docx", "txt", "md"].includes(ext)) return "document";
  if (["mp4", "mkv", "mov", "webm"].includes(ext)) return "video";
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("video/")) return "video";
  if (
    file.type.includes("pdf") ||
    file.type.includes("document") ||
    file.type.includes("text")
  )
    return "document";
  return null;
}

function buildNotebookItems(question: WrongQuestion): NotebookContentItem[] {
  const items: NotebookContentItem[] = [];
  splitNoteBlocks(question.notes ?? "").forEach((text, i) => {
    items.push({
      kind: "notes",
      label: `Note ${i + 1}`,
      text,
    });
  });
  const fileType = question.file_type;
  if (
    question.file_path &&
    ["image", "document", "video"].includes(fileType)
  ) {
    items.push({
      kind: "file",
      label: question.original_filename || question.title || "Attachment",
      questionId: question.id,
      fileType,
    });
  }
  return items;
}

function formatTextResult(
  result: TranslationResult,
  mode: TranslateMode
): string {
  return formatTranslationResult(result, mode);
}

function formatEnLearnResult(
  result: EnLearnTranslateResult,
  mode: TranslateMode
): string {
  if (mode === "bilingual" && result.pairs?.length) {
    return result.pairs.map((p) => `${p.source}\n${p.target}`).join("\n\n");
  }
  return result.chinese_text ?? result.full_text ?? "";
}

function formatVideoCue(
  result: VideoTranslationResult,
  index: number,
  mode: TranslateMode
): string {
  return formatVideoCueText(result, index, mode);
}

function ResultPanel({
  value,
  placeholder,
}: {
  value: string;
  placeholder: string;
}) {
  return (
    <Textarea
      readOnly
      value={value}
      placeholder={placeholder}
      className="min-h-[40vh] flex-1 resize-none bg-muted/30 md:min-h-0"
    />
  );
}

function MediaPreview({
  kind,
  src,
  filename,
}: {
  kind: UploadKind | "image" | "video" | "document" | null;
  src: string | null;
  filename?: string;
}) {
  if (!src) {
    return (
      <div className="text-muted-foreground flex flex-1 items-center justify-center p-6 text-sm">
        Preview appears here after you choose a file
      </div>
    );
  }
  if (kind === "image") {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt={filename ?? "preview"}
        className="max-h-full max-w-full object-contain"
      />
    );
  }
  if (kind === "video") {
    return (
      <video
        src={src}
        controls
        className="max-h-full max-w-full rounded-md"
        playsInline
      />
    );
  }
  return (
    <div className="flex flex-col items-center justify-center gap-2 p-6 text-center">
      <FileText className="text-muted-foreground size-10" />
      <p className="text-sm font-medium">{filename}</p>
      <p className="text-muted-foreground text-xs">Translation appears on the right</p>
    </div>
  );
}

export function TranslatorApp() {
  const [sourceTab, setSourceTab] = useState<SourceTab>("text");
  const [mode, setMode] = useState<TranslateMode>("bilingual");
  const [textInput, setTextInput] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [filePreviewUrl, setFilePreviewUrl] = useState<string | null>(null);
  const [uploadKind, setUploadKind] = useState<UploadKind | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<
    TranslationResult | VideoTranslationResult | null
  >(null);
  const [cueIndex, setCueIndex] = useState(0);
  const [toast, setToast] = useState<string | null>(null);
  const [enLearnResult, setEnLearnResult] = useState<EnLearnTranslateResult | null>(
    null
  );
  const [learningMode, setLearningMode] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState<number | null>(null);
  const [ttsError, setTtsError] = useState<string | null>(null);
  const ttsPlayback = useTtsPlayback({
    onHighlightIndex: setHighlightIndex,
    onError: setTtsError,
  });
  const { selectLine: selectTtsLine } = ttsPlayback;

  useEffect(() => {
    selectTtsLine(null);
  }, [enLearnResult, selectTtsLine]);

  const [notebookList, setNotebookList] = useState<WrongQuestion[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [selectedQuestion, setSelectedQuestion] = useState<WrongQuestion | null>(
    null
  );
  const [contentItems, setContentItems] = useState<NotebookContentItem[]>([]);
  const [contentIndex, setContentIndex] = useState(0);
  const [exportOpen, setExportOpen] = useState(false);
  const [exportFormat, setExportFormat] = useState<ExportFormat>("docx");
  const [exportEmail, setExportEmail] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    void getUserSettings()
      .then((s) => setExportEmail(s.translation_download_email))
      .catch(() => setExportEmail(null));
  }, []);

  const currentContent = contentItems[contentIndex] ?? null;
  const isVideoResult = result != null && "cues" in result;

  useEffect(() => {
    if (!file) {
      setFilePreviewUrl(null);
      setUploadKind(null);
      return;
    }
    setUploadKind(detectUploadKind(file));
    const url = URL.createObjectURL(file);
    setFilePreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const notebookMediaUrl = useMemo(() => {
    if (!selectedQuestion?.file_path) return null;
    if (currentContent?.kind !== "file") return null;
    if (!["image", "video"].includes(currentContent.fileType)) return null;
    return resolveUploadUrl(selectedQuestion.file_path);
  }, [selectedQuestion, currentContent]);

  const resultText = useMemo(() => {
    if (enLearnResult) {
      return formatEnLearnResult(enLearnResult, mode);
    }
    if (!result) return "";
    if ("cues" in result) {
      return formatVideoCue(result, cueIndex, mode);
    }
    return formatTextResult(result as TranslationResult, mode);
  }, [enLearnResult, result, mode, cueIndex]);

  const enLearnUnlocked = !!enLearnResult && !loading;

  const loadNotebookList = useCallback(async () => {
    try {
      setNotebookList(await listWrongQuestions());
    } catch {
      setNotebookList([]);
    }
  }, []);

  useEffect(() => {
    if (sourceTab === "notebook") void loadNotebookList();
  }, [sourceTab, loadNotebookList]);

  function handleFileChange(next: File | null) {
    setFile(next);
    setResult(null);
    setEnLearnResult(null);
    setCueIndex(0);
    setError(null);
    setLearningMode(false);
    setTtsError(null);
  }

  async function pickNotebookItem(item: WrongQuestion) {
    setPickerOpen(false);
    setError(null);
    setResult(null);
    setEnLearnResult(null);
    setCueIndex(0);
    setLearningMode(false);
    setTtsError(null);
    try {
      const detail = await getWrongQuestion(item.id);
      const items = buildNotebookItems(detail);
      if (items.length === 0) {
        setError("This item has no notes or attachments to translate");
        setSelectedQuestion(null);
        setContentItems([]);
        return;
      }
      setSelectedQuestion(detail);
      setContentItems(items);
      setContentIndex(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load material");
    }
  }

  async function handleTranslate() {
    setLoading(true);
    setError(null);
    setToast(null);
    setResult(null);
    setEnLearnResult(null);
    setCueIndex(0);
    setLearningMode(false);
    setTtsError(null);

    try {
      if (sourceTab === "text") {
        if (!textInput.trim()) {
          setError("Enter English text");
          return;
        }
        setEnLearnResult(
          await enLearnTranslateText({ text: textInput.trim(), mode })
        );
      } else if (sourceTab === "upload") {
        if (!file || !uploadKind) {
          setError("Choose a supported file");
          return;
        }
        if (uploadKind === "image") {
          setEnLearnResult(await enLearnTranslateImage(file, mode));
        } else if (uploadKind === "document") {
          setResult(await translateDocument(file, { mode }));
        } else {
          setResult(
            await translateVideo(file, {
              subtitle_mode: mode === "bilingual" ? "bilingual" : "translated",
            })
          );
        }
      } else {
        if (!currentContent) {
          setError("Select notebook material and content first");
          return;
        }
        if (currentContent.kind === "notes") {
          setResult(
            await translateText({ text: currentContent.text, mode })
          );
        } else {
          setResult(
            await translateFromNotebook({
              question_id: currentContent.questionId,
              mode,
              subtitle_mode:
                currentContent.fileType === "video"
                  ? mode === "bilingual"
                    ? "bilingual"
                    : "translated"
                  : undefined,
            })
          );
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Translation failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveToNotebook() {
    if (!result) return;
    const questionId =
      result.notebook?.question_id ?? selectedQuestion?.id ?? null;
    if (!questionId) {
      setError("Select a notebook item before saving");
      return;
    }
    const content =
      "cues" in result
        ? formatVideoResultText(result, mode)
        : formatTextResult(result, mode);
    setLoading(true);
    try {
      await saveTranslationToNotebook({
        question_id: questionId,
        content,
        append: true,
      });
      setToast("Saved to notebook");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleEmailExport() {
    if (!resultText) return;
    if (!exportEmail?.trim()) {
      setExportOpen(true);
      return;
    }
    setExporting(true);
    setError(null);
    try {
      const data = await emailTranslationExport({
        content: resultText,
        export_format: exportFormat,
        title: "Translation",
      });
      setToast(`Sent to ${data.email}`);
      setExportOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Email export failed");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs
          value={sourceTab}
          onValueChange={(v) => {
            setSourceTab(v as SourceTab);
            setError(null);
            setResult(null);
            setEnLearnResult(null);
            setLearningMode(false);
            setTtsError(null);
          }}
        >
          <TabsList>
            <TabsTrigger value="text">Text</TabsTrigger>
            <TabsTrigger value="upload">Upload</TabsTrigger>
            <TabsTrigger value="notebook">Notebook</TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="flex rounded-lg border p-0.5">
          <button
            type="button"
            className={cn(
              "rounded-md px-3 py-1.5 text-sm transition-colors",
              mode === "full"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
            onClick={() => setMode("full")}
          >
            Translation
          </button>
          <button
            type="button"
            className={cn(
              "rounded-md px-3 py-1.5 text-sm transition-colors",
              mode === "bilingual"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
            onClick={() => setMode("bilingual")}
          >
            Bilingual
          </button>
        </div>
      </div>

      <div className="relative grid min-h-0 flex-1 gap-3 md:grid-cols-2">
        <TranslationLoadingOverlay open={loading} />
        <div className="flex min-h-[45vh] flex-col overflow-hidden rounded-lg border md:min-h-0">
          {sourceTab === "text" && (
            <Textarea
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              placeholder="Enter English"
              className="min-h-[45vh] flex-1 resize-none border-0 shadow-none focus-visible:ring-0 md:min-h-0"
            />
          )}

          {sourceTab === "upload" && (
            <>
              <label className="relative flex flex-1 cursor-pointer flex-col overflow-hidden">
                <div className="flex flex-1 items-center justify-center overflow-auto bg-muted/10 p-3">
                  <MediaPreview
                    kind={uploadKind}
                    src={filePreviewUrl}
                    filename={file?.name}
                  />
                </div>
                {!file && (
                  <div className="text-muted-foreground border-t py-3 text-center text-xs">
                    Click to choose image, document, or video
                  </div>
                )}
                <input
                  type="file"
                  className="absolute inset-0 cursor-pointer opacity-0"
                  accept="image/*,.pdf,.docx,.txt,.md,video/*,.mp4,.mkv,.mov,.webm"
                  onChange={(e) =>
                    handleFileChange(e.target.files?.[0] ?? null)
                  }
                />
              </label>
              {file && (
                <div className="text-muted-foreground border-t px-3 py-2 text-xs">
                  {file.name} · click preview to replace file
                </div>
              )}
            </>
          )}

          {sourceTab === "notebook" && (
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="flex flex-wrap items-center gap-2 border-b p-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPickerOpen(true)}
                >
                  {selectedQuestion ? selectedQuestion.title : "Choose material"}
                </Button>
                {contentItems.length > 0 && (
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      disabled={contentIndex <= 0}
                      onClick={() => {
                        setContentIndex((i) => i - 1);
                        setResult(null);
                        setCueIndex(0);
                      }}
                    >
                      <ChevronLeft className="size-4" />
                    </Button>
                    <span className="text-muted-foreground text-xs">
                      {contentIndex + 1}/{contentItems.length}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      disabled={contentIndex >= contentItems.length - 1}
                      onClick={() => {
                        setContentIndex((i) => i + 1);
                        setResult(null);
                        setCueIndex(0);
                      }}
                    >
                      <ChevronRight className="size-4" />
                    </Button>
                  </div>
                )}
              </div>
              <div className="flex flex-1 items-center justify-center overflow-auto bg-muted/10 p-3">
                {currentContent?.kind === "file" &&
                ["image", "video"].includes(currentContent.fileType) &&
                notebookMediaUrl ? (
                  <MediaPreview
                    kind={currentContent.fileType as UploadKind}
                    src={notebookMediaUrl}
                    filename={currentContent.label}
                  />
                ) : (
                  <Textarea
                    readOnly
                    value={
                      currentContent?.kind === "notes" ? currentContent.text : ""
                    }
                    placeholder="Preview note content after choosing material"
                    className="h-full min-h-[200px] resize-none border-0 bg-transparent shadow-none"
                  />
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex min-h-[45vh] flex-col overflow-hidden rounded-lg border md:min-h-0">
          {resultText || (enLearnUnlocked && enLearnResult) ? (
            <div className="flex flex-wrap items-center justify-end gap-1 border-b bg-muted/20 px-2 py-1.5">
              <TooltipProvider delay={300}>
                {enLearnUnlocked && enLearnResult && (
                  <TtsReadAloudBar
                    text={enLearnResult.corrected_text}
                    variant="inline"
                    playback={ttsPlayback}
                  />
                )}
                {enLearnUnlocked ? (
                  <Tooltip>
                    <TooltipTrigger
                      className={cn(
                        "inline-flex size-7 items-center justify-center rounded-md transition-colors hover:bg-muted",
                        learningMode && "bg-secondary text-secondary-foreground"
                      )}
                      aria-label="Study mode"
                      aria-pressed={learningMode}
                      disabled={!enLearnUnlocked}
                      onClick={() => setLearningMode((v) => !v)}
                    >
                      <GraduationCap className="size-3.5" />
                    </TooltipTrigger>
                    <TooltipContent>Study mode</TooltipContent>
                  </Tooltip>
                ) : null}
                {resultText ? (
                  <Tooltip>
                    <TooltipTrigger
                      className="inline-flex size-7 items-center justify-center rounded-md transition-colors hover:bg-muted"
                      aria-label="Email export"
                      onClick={() => setExportOpen(true)}
                    >
                      <Mail className="size-3.5" />
                    </TooltipTrigger>
                    <TooltipContent>Email export</TooltipContent>
                  </Tooltip>
                ) : null}
              </TooltipProvider>
            </div>
          ) : null}
          {enLearnResult ? (
            <WordLearningProvider enabled={learningMode && enLearnUnlocked}>
              <CorrectedBilingualPanel
                correctedText={enLearnResult.corrected_text}
                errors={enLearnResult.error_list}
                chineseText={enLearnResult.chinese_text ?? ""}
                pairs={enLearnResult.pairs}
                learningMode={learningMode}
                highlightSentenceIndex={highlightIndex}
                playback={ttsPlayback}
              />
            </WordLearningProvider>
          ) : (
            <>
              {isVideoResult &&
                result &&
                "cues" in result &&
                result.cues.length > 0 && (
                  <div className="flex items-center justify-end gap-1 border-b px-2 py-1">
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      disabled={cueIndex <= 0}
                      onClick={() => setCueIndex((i) => i - 1)}
                    >
                      <ChevronLeft className="size-4" />
                    </Button>
                    <span className="text-muted-foreground text-xs">
                      Subtitle {cueIndex + 1}/{result.cues.length}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      disabled={cueIndex >= result.cues.length - 1}
                      onClick={() => setCueIndex((i) => i + 1)}
                    >
                      <ChevronRight className="size-4" />
                    </Button>
                  </div>
                )}
              <ResultPanel value={resultText} placeholder="Translation" />
            </>
          )}
        </div>
      </div>

      {error && (
        <p className="text-destructive text-sm" role="alert">
          {error}
        </p>
      )}
      {toast && (
        <p className="text-sm text-green-600 dark:text-green-400">{toast}</p>
      )}
      {ttsError && (
        <p className="text-destructive text-sm" role="alert">
          Read aloud: {ttsError}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2 border-t pt-3">
        <Button onClick={() => void handleTranslate()} disabled={loading}>
          {loading ? "Translating…" : "Translate"}
        </Button>
        {sourceTab === "notebook" && (
          <Button
            variant="outline"
            size="sm"
            disabled={!result || loading}
            onClick={() => void handleSaveToNotebook()}
          >
            <Save className="mr-1 size-4" />
            Save to notebook
          </Button>
        )}
      </div>

      <Dialog open={pickerOpen} onOpenChange={setPickerOpen}>
        <DialogContent className="max-h-[70vh] overflow-hidden sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Choose notebook material</DialogTitle>
          </DialogHeader>
          <div className="max-h-[50vh] overflow-y-auto">
            {notebookList.length === 0 ? (
              <p className="text-muted-foreground py-6 text-center text-sm">
                No materials yet
              </p>
            ) : (
              <ul className="flex flex-col gap-1">
                {notebookList.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className="hover:bg-muted w-full rounded-lg px-3 py-2.5 text-left text-sm transition-colors"
                      onClick={() => void pickNotebookItem(item)}
                    >
                      <div className="font-medium">{item.title}</div>
                      <div className="text-muted-foreground text-xs">
                        {item.category_name} · {item.file_type}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={exportOpen} onOpenChange={setExportOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Email translation export</DialogTitle>
            <DialogDescription>
              Choose a format. The file is sent to your bound email — not downloaded
              in the browser.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <label
                htmlFor="export-format"
                className="text-sm font-medium leading-none"
              >
                Format
              </label>
              <select
                id="export-format"
                className="border-input bg-background h-9 w-full rounded-md border px-3 text-sm"
                value={exportFormat}
                onChange={(e) => setExportFormat(e.target.value as ExportFormat)}
              >
                <option value="docx">Word (.docx)</option>
                <option value="pdf">PDF (.pdf)</option>
                <option value="txt">Plain text (.txt)</option>
              </select>
            </div>
            {exportEmail?.trim() ? (
              <p className="text-muted-foreground text-sm">
                Sending to:{" "}
                <span className="text-foreground font-medium">{exportEmail}</span>
              </p>
            ) : (
              <p className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-900 dark:text-amber-100">
                No download email set.{" "}
                <Link href="/settings" className="font-medium underline underline-offset-2">
                  Open Settings
                </Link>{" "}
                to bind an address first.
              </p>
            )}
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setExportOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!exportEmail?.trim() || exporting || !resultText}
              onClick={() => void handleEmailExport()}
            >
              {exporting ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  Sending…
                </>
              ) : (
                "Send email"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
