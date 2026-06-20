"use client";

import type { ErrorItem } from "@/lib/api/en-learn";
import { splitEnglishLines, type TtsPlaybackState } from "@/hooks/use-tts-playback";
import { cn } from "@/lib/utils";

import { TtsLineReadButton } from "@/components/en-learn/tts-read-aloud-bar";
import { LearningWord } from "@/components/en-learn/word-learning-layer";

type Props = {
  correctedText: string;
  errors: ErrorItem[];
  chineseText: string;
  pairs?: { source: string; target: string }[];
  learningMode?: boolean;
  highlightSentenceIndex?: number | null;
  playback?: TtsPlaybackState;
};

function renderEnglishTokens(
  text: string,
  errorByWord: Map<string, ErrorItem>,
  learningMode?: boolean
) {
  return text.split(/(\s+|[,.;:!?()])/).map((tok, i) => {
    const clean = tok.replace(/[^a-zA-Z'-]/g, "");
    const err = clean ? errorByWord.get(clean.toLowerCase()) : undefined;
    const isWord = clean.length > 1 && /[a-zA-Z]/.test(tok);

    if (!isWord) {
      return <span key={`${i}-${tok}`}>{tok}</span>;
    }

    const inner = (
      <>
        {tok}
        {err && (
          <span className="text-muted-foreground ml-0.5 text-xs">
            ({err.correction})
          </span>
        )}
      </>
    );

    if (learningMode) {
      return (
        <LearningWord
          key={`${i}-${tok}`}
          word={clean}
          className={cn(
            err ? "text-red-600 dark:text-red-400" : "text-foreground"
          )}
        >
          {inner}
        </LearningWord>
      );
    }

    return (
      <span
        key={`${i}-${tok}`}
        className={cn(err ? "text-red-600 dark:text-red-400" : "text-foreground")}
      >
        {inner}
      </span>
    );
  });
}

type LineBlock = {
  index: number;
  source: string;
  target: string | null;
};

function buildLineBlocks(
  correctedText: string,
  chineseText: string,
  pairs?: { source: string; target: string }[]
): LineBlock[] {
  if (pairs && pairs.length > 0) {
    return pairs.map((p, index) => ({
      index,
      source: p.source,
      target: p.target,
    }));
  }
  return splitEnglishLines(correctedText).map((source, index) => ({
    index,
    source,
    target: index === 0 ? chineseText || null : null,
  }));
}

export function CorrectedBilingualPanel({
  correctedText,
  errors,
  chineseText,
  pairs,
  learningMode,
  highlightSentenceIndex,
  playback,
}: Props) {
  const errorByWord = new Map(errors.map((e) => [e.word.toLowerCase(), e]));
  const lines = buildLineBlocks(correctedText, chineseText, pairs);
  const showFullChinese =
    !pairs?.length && lines.length > 1 && chineseText.trim().length > 0;

  return (
    <div className="min-h-[45vh] flex-1 overflow-auto bg-muted/30 p-3 text-sm md:min-h-0">
      <div className="flex flex-col gap-3">
        {lines.map((line) => {
          const selected = playback?.selectedLineIndex === line.index;
          const highlighted = highlightSentenceIndex === line.index;

          return (
            <div
              key={line.index}
              role="button"
              tabIndex={0}
              className={cn(
                "cursor-pointer rounded-md border border-transparent px-2 py-1.5 transition-colors",
                highlighted && "bg-primary/10",
                selected && "border-primary/30 bg-muted/50",
                !selected && !highlighted && "hover:bg-muted/40"
              )}
              onClick={() => playback?.selectLine(line.index)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  playback?.selectLine(line.index);
                }
              }}
            >
              <div className="flex items-start gap-2">
                <div className="min-w-0 flex-1">
                  <p className="leading-relaxed">
                    {renderEnglishTokens(line.source, errorByWord, learningMode)}
                  </p>
                  {line.target && !showFullChinese && (
                    <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
                      {line.target}
                    </p>
                  )}
                </div>
                {playback && (
                  <TtsLineReadButton
                    lineIndex={line.index}
                    text={line.source}
                    playback={playback}
                    visible={selected || highlighted}
                  />
                )}
              </div>
            </div>
          );
        })}
        {showFullChinese && (
          <p className="text-muted-foreground border-t pt-3 text-sm leading-relaxed whitespace-pre-wrap">
            {chineseText}
          </p>
        )}
      </div>
    </div>
  );
}
