"use client";

import { useState } from "react";
import { BookOpen, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { TranslationLoadingOverlay } from "@/components/translator/translation-loading-overlay";
import { CorrectedBilingualPanel } from "@/components/en-learn/corrected-bilingual-panel";
import { TtsReadAloudBar } from "@/components/en-learn/tts-read-aloud-bar";
import { WordLearningLayer } from "@/components/en-learn/word-learning-layer";
import { useTtsPlayback } from "@/hooks/use-tts-playback";
import {
  enLearnTranslateImage,
  enLearnTranslateText,
  type EnLearnTranslateResult,
} from "@/lib/api/en-learn";
import { cn } from "@/lib/utils";

export function EnLearnTranslatorApp() {
  const [textInput, setTextInput] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EnLearnTranslateResult | null>(null);
  const [learningMode, setLearningMode] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState<number | null>(null);
  const ttsPlayback = useTtsPlayback({ onHighlightIndex: setHighlightIndex });

  const unlocked = !!result && !loading;

  async function handleTranslate() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      if (file) {
        setResult(await enLearnTranslateImage(file, "bilingual"));
      } else {
        if (!textInput.trim()) {
          setError("Enter English text");
          return;
        }
        setResult(await enLearnTranslateText({ text: textInput.trim(), mode: "bilingual" }));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Translation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">
          Smart translation · correction · read-aloud · vocabulary
        </h2>
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={learningMode}
            disabled={!unlocked}
            onChange={(e) => setLearningMode(e.target.checked)}
          />
          <BookOpen className="size-4" />
          Study mode
          {!unlocked && (
            <span className="text-muted-foreground text-xs">(unlocks after translation)</span>
          )}
        </label>
      </div>

      <div className="relative grid min-h-0 flex-1 gap-3 md:grid-cols-2">
        <TranslationLoadingOverlay open={loading} />
        <div className="flex min-h-[40vh] flex-col overflow-hidden rounded-lg border md:min-h-0">
          <Textarea
            value={textInput}
            onChange={(e) => {
              setTextInput(e.target.value);
              setFile(null);
            }}
            placeholder="Paste English or choose an image for OCR"
            className="min-h-[200px] flex-1 resize-none border-0 shadow-none focus-visible:ring-0"
          />
          <label className="border-t px-3 py-2 text-xs">
            <input
              type="file"
              accept="image/*"
              className="mr-2"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setTextInput("");
              }}
            />
            Image OCR translation
          </label>
        </div>

        <div className="flex min-h-[40vh] flex-col overflow-hidden rounded-lg border md:min-h-0">
          <TtsReadAloudBar
            text={result?.corrected_text ?? ""}
            disabled={!unlocked}
            variant="bar"
            playback={ttsPlayback}
          />
          <WordLearningLayer enabled={learningMode && unlocked}>
            {result ? (
              <CorrectedBilingualPanel
                correctedText={result.corrected_text}
                errors={result.error_list}
                chineseText={result.chinese_text ?? ""}
                pairs={result.pairs}
                learningMode={learningMode}
                highlightSentenceIndex={highlightIndex}
                playback={ttsPlayback}
              />
            ) : (
              <div className="text-muted-foreground flex flex-1 items-center justify-center p-6 text-sm">
                Corrected English and Chinese translation appear here
              </div>
            )}
          </WordLearningLayer>
        </div>
      </div>

      {error && (
        <p className="text-destructive text-sm" role="alert">
          {error}
        </p>
      )}

      <div className="flex items-center gap-2">
        <Button onClick={() => void handleTranslate()} disabled={loading}>
          {loading ? (
            <>
              <Loader2 className="mr-2 size-4 animate-spin" />
              Translating…
            </>
          ) : (
            "Translate"
          )}
        </Button>
        <span
          className={cn(
            "text-muted-foreground text-xs",
            unlocked && "text-green-600 dark:text-green-400"
          )}
        >
          {unlocked
            ? "Read-aloud and word lookup unlocked"
            : "Complete translation to unlock read-aloud and vocabulary"}
        </span>
      </div>
    </div>
  );
}
