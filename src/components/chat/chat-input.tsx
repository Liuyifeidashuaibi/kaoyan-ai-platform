"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bot,
  ChevronDown,
  FileText,
  Loader2,
  MessageSquare,
  Mic,
  Paperclip,
  Send,
  Square,
  Volume2,
  X,
} from "lucide-react";

import { transcribeAudio } from "@/lib/api/chat";
import { WavRecorder } from "@/lib/audio/wav-recorder";
import { cn } from "@/lib/utils";

const ALLOWED_IMG_MIME = new Set([
  "image/jpeg",
  "image/png",
  "image/gif",
  "image/webp",
]);
const ALLOWED_IMG_EXT = new Set(["jpg", "jpeg", "png", "gif", "webp"]);
const ALLOWED_DOC_EXT = new Set(["pdf", "docx", "doc", "txt", "md", "csv"]);
const HEIC_EXT = new Set(["heic", "heif"]);
const HEIC_MIME = new Set(["image/heic", "image/heif"]);
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MAX_DOC_BYTES = 10 * 1024 * 1024;
const MAX_AUDIO_SECONDS = 30;

const FILE_INPUT_ACCEPT =
  "image/jpeg,image/png,image/gif,image/webp,.jpg,.jpeg,.png,.gif,.webp,.pdf,.docx,.doc,.txt,.md,.csv";

type AttachState = "idle" | "loading" | "ready" | "error";
type AttachKind = "image" | "document" | null;

export type ChatSendPayload = {
  content: string;
  imageFile: File | null;
  previewUrl: string | null;
  audioFile: Blob | null;
  enableTts: boolean;
  docFile: File | null;
};

type ChatInputProps = {
  onSend: (payload: ChatSendPayload) => void;
  onStop?: () => void;
  disabled?: boolean;
  isStreaming?: boolean;
  placeholder?: string;
  chatMode?: "chat" | "agent";
  onModeChange?: (mode: "chat" | "agent") => void;
};

function isImageFile(file: File): boolean {
  if (ALLOWED_IMG_MIME.has(file.type)) return true;
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  return ALLOWED_IMG_EXT.has(ext);
}

function isDocumentFile(file: File): boolean {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  return ALLOWED_DOC_EXT.has(ext);
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatSeconds(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function appendTranscript(prev: string, next: string): string {
  const a = prev.trimEnd();
  const b = next.trim();
  if (!b) return a;
  if (!a) return b;
  return `${a} ${b}`;
}

export function ChatInput({
  onSend,
  onStop,
  disabled,
  isStreaming,
  placeholder = "Ask anything…",
  chatMode = "chat",
  onModeChange,
}: ChatInputProps) {
  const [content, setContent] = useState("");
  const [attachFile, setAttachFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [attachState, setAttachState] = useState<AttachState>("idle");
  const [attachKind, setAttachKind] = useState<AttachKind>(null);
  const [imageHint, setImageHint] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [enableTts, setEnableTts] = useState(false);
  const [modeDropdownOpen, setModeDropdownOpen] = useState(false);

  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const previewUrlRef = useRef<string | null>(null);
  const wavRecorderRef = useRef<WavRecorder | null>(null);
  const recordTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const modeDropdownRef = useRef<HTMLDivElement>(null);

  const revokePreview = useCallback(() => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    setPreviewUrl(null);
  }, []);

  useEffect(() => () => {
    revokePreview();
    if (recordTimerRef.current) clearInterval(recordTimerRef.current);
    if (wavRecorderRef.current?.isActive) {
      wavRecorderRef.current.stop();
    }
  }, [revokePreview]);

  // Close mode dropdown on outside click
  useEffect(() => {
    if (!modeDropdownOpen) return;
    const handler = (e: MouseEvent) => {
      if (modeDropdownRef.current && !modeDropdownRef.current.contains(e.target as Node)) {
        setModeDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [modeDropdownOpen]);

  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  useEffect(() => {
    resizeTextarea();
  }, [content, resizeTextarea]);

  const clearAttach = useCallback(() => {
    revokePreview();
    setAttachFile(null);
    setAttachState("idle");
    setAttachKind(null);
    setImageHint(null);
  }, [revokePreview]);

  const transcribeAndAppend = useCallback(async (wav: Blob) => {
    setIsTranscribing(true);
    setImageHint("Transcribing audio…");
    try {
      const text = await transcribeAudio(wav);
      setContent((prev) => appendTranscript(prev, text));
      setImageHint(null);
      requestAnimationFrame(() => {
        textareaRef.current?.focus();
        const el = textareaRef.current;
        if (el) {
          el.selectionStart = el.selectionEnd = el.value.length;
        }
      });
    } catch (e) {
      setImageHint(e instanceof Error ? e.message : "Speech recognition failed. Try again.");
    } finally {
      setIsTranscribing(false);
      setRecordSeconds(0);
    }
  }, []);

  const stopRecording = useCallback(async () => {
    if (recordTimerRef.current) {
      clearInterval(recordTimerRef.current);
      recordTimerRef.current = null;
    }
    const recorder = wavRecorderRef.current;
    wavRecorderRef.current = null;
    setIsRecording(false);

    if (!recorder?.isActive) return;

    const wav = recorder.stop();
    if (wav.size > 0) {
      await transcribeAndAppend(wav);
    } else {
      setImageHint("Recording too short. Try again.");
      setRecordSeconds(0);
    }
  }, [transcribeAndAppend]);

  const startRecording = useCallback(async () => {
    if (isRecording || isTranscribing || disabled || isStreaming) return;
    try {
      const recorder = new WavRecorder();
      await recorder.start();
      wavRecorderRef.current = recorder;
      setIsRecording(true);
      setRecordSeconds(0);
      setImageHint(null);
      recordTimerRef.current = setInterval(() => {
        setRecordSeconds((s) => {
          if (s + 1 >= MAX_AUDIO_SECONDS) {
            void stopRecording();
            return MAX_AUDIO_SECONDS;
          }
          return s + 1;
        });
      }, 1000);
    } catch {
      setImageHint("Microphone access denied. Check browser permissions.");
    }
  }, [disabled, isRecording, isStreaming, isTranscribing, stopRecording]);

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      e.target.value = "";
      if (!file) return;

      const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
      const isImg = isImageFile(file);
      const isDoc = isDocumentFile(file);

      // HEIC check
      if (HEIC_MIME.has(file.type) || HEIC_EXT.has(ext)) {
        clearAttach();
        setAttachState("error");
        setImageHint("HEIC format is not supported. Export as JPEG from your photo library.");
        return;
      }

      if (!isImg && !isDoc) {
        clearAttach();
        setAttachState("error");
        setImageHint("Unsupported file type. Supported: images, PDF, DOCX, TXT, MD, CSV");
        return;
      }

      const maxBytes = isImg ? MAX_IMAGE_BYTES : MAX_DOC_BYTES;
      if (file.size > maxBytes) {
        clearAttach();
        setAttachState("error");
        setImageHint(`File too large (over ${maxBytes === MAX_IMAGE_BYTES ? "5" : "10"}MB)`);
        return;
      }

      revokePreview();
      setAttachFile(null);
      setAttachState("loading");
      setAttachKind(isImg ? "image" : "document");
      setImageHint(isImg ? "Loading image…" : "Loading file…");

      // For images, create preview URL
      if (isImg) {
        const objectUrl = URL.createObjectURL(file);
        previewUrlRef.current = objectUrl;
        setPreviewUrl(objectUrl);
      }

      try {
        const buffer = await file.arrayBuffer();
        if (buffer.byteLength === 0) throw new Error("empty");
        setAttachFile(file);
        setAttachState("ready");
        setAttachKind(isImg ? "image" : "document");
        setImageHint(null);
      } catch {
        revokePreview();
        setAttachFile(null);
        setAttachState("error");
        setAttachKind(null);
        setImageHint("Failed to read file. Please select again.");
      }
    },
    [clearAttach, revokePreview]
  );

  const trimmed = content.trim();
  const hasAttach = attachState !== "idle";
  const attachReady = attachState === "ready" && attachFile !== null;
  const attachPending = attachState === "loading";
  const voiceBusy = isRecording || isTranscribing;

  const canSend =
    (!!trimmed && !hasAttach) || attachReady || (!!trimmed && attachReady);

  const handleSend = useCallback(() => {
    if (isStreaming) {
      onStop?.();
      return;
    }
    if (voiceBusy) return;
    if (attachPending) return;
    if (hasAttach && !attachReady) return;
    if (!canSend) return;

    const isImg = attachReady && attachKind === "image" && attachFile;
    const isDoc = attachReady && attachKind === "document" && attachFile;

    let text = trimmed;
    // For documents, append filename to content
    if (isDoc && !trimmed) {
      text = `请分析这份文件：${attachFile!.name}`;
    } else if (isDoc && trimmed) {
      text = `${trimmed}\n\n[附件: ${attachFile!.name}]`;
    } else if (isImg && !trimmed) {
      text = "Please analyze this problem";
    }

    const fileToSend = isImg ? attachFile : null;
    const previewToSend = isImg ? previewUrlRef.current : null;
    const docToSend = isDoc ? attachFile : null;

    onSend({
      content: text,
      imageFile: fileToSend,
      previewUrl: previewToSend,
      audioFile: null,
      enableTts,
      docFile: docToSend,
    });

    setContent("");
    if (attachFile) {
      previewUrlRef.current = null;
      setPreviewUrl(null);
      setAttachFile(null);
      setAttachState("idle");
      setAttachKind(null);
      setImageHint(null);
    } else {
      clearAttach();
    }
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }, [
    canSend,
    clearAttach,
    enableTts,
    hasAttach,
    attachFile,
    attachKind,
    attachPending,
    attachReady,
    isStreaming,
    onSend,
    onStop,
    trimmed,
    voiceBusy,
  ]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const showStop = isStreaming;
  const sendDisabled =
    !showStop &&
    (disabled ||
      voiceBusy ||
      attachPending ||
      (hasAttach && !attachReady) ||
      !canSend);

  const footerHint = (() => {
    if (isRecording) {
      return `Recording ${formatSeconds(recordSeconds)} / max ${MAX_AUDIO_SECONDS}s — tap mic to stop`;
    }
    if (isTranscribing) return "Converting speech to text…";
    if (attachPending) return "Loading file…";
    if (hasAttach && attachState === "error") return imageHint;
    if (imageHint) return imageHint;
    return "Tap mic to dictate, edit, and send · Enter to send";
  })();

  const footerHintWarning =
    isRecording ||
    isTranscribing ||
    attachPending ||
    (hasAttach && attachState === "error") ||
    !!imageHint;

  return (
    <div className="shrink-0 border-t border-border bg-background/95 px-4 py-3 backdrop-blur md:px-6">
      <div className="mx-auto max-w-3xl">
        {/* Attachment preview */}
        {previewUrl && attachKind === "image" && (
          <div className="mb-2">
            <div className="relative inline-block">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={previewUrl}
                alt="Selected image preview"
                className="max-h-28 max-w-full rounded-xl border border-border object-contain bg-muted/30"
              />
              {attachPending && (
                <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-black/40">
                  <div className="size-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                </div>
              )}
              {!isStreaming && (
                <button
                  type="button"
                  onClick={clearAttach}
                  className="absolute -top-1.5 -right-1.5 flex size-5 items-center justify-center rounded-full bg-foreground/80 text-background hover:bg-foreground"
                  aria-label="Remove attachment"
                >
                  <X className="size-3" />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Document file card preview */}
        {attachReady && attachKind === "document" && attachFile && (
          <div className="mb-2">
            <div className="relative inline-flex items-center gap-2.5 rounded-xl border border-border bg-muted/40 py-2 pl-3 pr-8">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                <FileText className="size-4 text-primary" />
              </div>
              <div className="flex flex-col">
                <span className="max-w-[200px] truncate text-xs font-medium text-foreground">
                  {attachFile.name}
                </span>
                <span className="text-[10px] text-muted-foreground">
                  {formatBytes(attachFile.size)}
                </span>
              </div>
              {!isStreaming && (
                <button
                  type="button"
                  onClick={clearAttach}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 flex size-5 items-center justify-center rounded-full bg-foreground/80 text-background hover:bg-foreground"
                  aria-label="Remove attachment"
                >
                  <X className="size-3" />
                </button>
              )}
            </div>
          </div>
        )}

        <div className="flex items-end gap-2 rounded-2xl border border-border bg-muted/30 px-3 py-2 focus-within:border-primary/50 focus-within:bg-background transition-colors">
          <input
            ref={fileRef}
            type="file"
            accept={FILE_INPUT_ACCEPT}
            className="hidden"
            onChange={handleFileChange}
          />

          {/* Mode dropdown */}
          {onModeChange && (
            <div ref={modeDropdownRef} className="relative shrink-0">
              <button
                type="button"
                onClick={() => setModeDropdownOpen((v) => !v)}
                disabled={isStreaming}
                className={cn(
                  "mb-0.5 flex h-8 shrink-0 items-center gap-1 rounded-lg px-2 text-xs font-medium transition-colors",
                  chatMode === "agent"
                    ? "text-primary"
                    : "text-muted-foreground hover:text-foreground",
                  isStreaming && "cursor-not-allowed opacity-50"
                )}
                aria-label="Select mode"
              >
                {chatMode === "chat" ? (
                  <MessageSquare className="size-4.5" />
                ) : (
                  <Bot className="size-4.5" />
                )}
                <span className="hidden sm:inline">
                  {chatMode === "chat" ? "Chat" : "Agent"}
                </span>
                <ChevronDown className="size-3 text-muted-foreground/50" />
              </button>
              {modeDropdownOpen && (
                <div className="absolute bottom-full left-0 z-50 mb-1.5 w-32 overflow-hidden rounded-lg border border-border bg-background shadow-lg">
                  <button
                    type="button"
                    onClick={() => {
                      onModeChange("chat");
                      setModeDropdownOpen(false);
                    }}
                    className={cn(
                      "flex w-full items-center gap-2 px-3 py-2 text-xs transition-colors hover:bg-muted",
                      chatMode === "chat"
                        ? "font-medium text-foreground"
                        : "text-muted-foreground"
                    )}
                  >
                    <MessageSquare className="size-4" />
                    Chat
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onModeChange("agent");
                      setModeDropdownOpen(false);
                    }}
                    className={cn(
                      "flex w-full items-center gap-2 px-3 py-2 text-xs transition-colors hover:bg-muted",
                      chatMode === "agent"
                        ? "font-medium text-primary"
                        : "text-muted-foreground"
                    )}
                  >
                    <Bot className="size-4" />
                    Agent
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Attachment button */}
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={disabled || isStreaming || attachPending || voiceBusy}
            className={cn(
              "mb-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg transition-colors",
              disabled || isStreaming || attachPending || voiceBusy
                ? "cursor-not-allowed text-muted-foreground/40"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
            aria-label="Attach file"
          >
            <Paperclip className="size-4.5" />
          </button>

          <button
            type="button"
            onClick={() => {
              if (isRecording) void stopRecording();
              else void startRecording();
            }}
            disabled={disabled || isStreaming || attachPending || isTranscribing}
            className={cn(
              "mb-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg transition-colors",
              isRecording
                ? "bg-destructive text-destructive-foreground animate-pulse"
                : isTranscribing
                  ? "cursor-wait text-muted-foreground"
                  : disabled || isStreaming || attachPending
                    ? "cursor-not-allowed text-muted-foreground/40"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
            aria-label={isRecording ? "Stop recording and transcribe" : "Voice input"}
          >
            {isTranscribing ? (
              <Loader2 className="size-4.5 animate-spin" />
            ) : (
              <Mic className="size-4.5" />
            )}
          </button>

          <button
            type="button"
            onClick={() => setEnableTts((v) => !v)}
            disabled={disabled || isStreaming}
            title="Read answer aloud when complete (optional)"
            className={cn(
              "mb-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg transition-colors",
              enableTts
                ? "bg-primary/15 text-primary"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
              (disabled || isStreaming) && "cursor-not-allowed opacity-40"
            )}
            aria-label="Text-to-speech toggle"
            aria-pressed={enableTts}
          >
            <Volume2 className="size-4.5" />
          </button>

          <textarea
            ref={textareaRef}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isStreaming
                ? "AI is responding…"
                : isTranscribing
                  ? "Transcribing…"
                  : attachReady
                    ? "Add a note or send…"
                    : placeholder
            }
            disabled={(disabled && !isStreaming) || isRecording || isTranscribing}
            rows={1}
            className="flex-1 resize-none bg-transparent py-1.5 text-sm leading-relaxed outline-none placeholder:text-muted-foreground/60 disabled:cursor-not-allowed"
            style={{ maxHeight: "200px" }}
          />

          <button
            type="button"
            onClick={handleSend}
            disabled={sendDisabled}
            className={cn(
              "mb-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg transition-colors",
              showStop
                ? "bg-foreground text-background hover:bg-foreground/80"
                : canSend && !disabled && !attachPending && !voiceBusy
                  ? "bg-primary text-primary-foreground hover:bg-primary/90"
                  : "cursor-not-allowed bg-muted text-muted-foreground/40"
            )}
            aria-label={showStop ? "Stop generating" : "Send"}
          >
            {showStop ? (
              <Square className="size-3.5 fill-current" />
            ) : (
              <Send className="size-3.5" />
            )}
          </button>
        </div>

        <p
          className={cn(
            "mt-1.5 text-center text-[11px]",
            footerHintWarning
              ? "text-amber-600 dark:text-amber-400"
              : "text-muted-foreground/50"
          )}
        >
          {footerHint}
        </p>
      </div>
    </div>
  );
}
