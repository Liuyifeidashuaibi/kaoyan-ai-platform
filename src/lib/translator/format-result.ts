import type {
  TranslationResult,
  VideoTranslationResult,
} from "@/lib/api/types";

export type TranslateDisplayMode = "full" | "bilingual";

export function normalizeTranslationResult<T extends TranslationResult>(result: T): T {
  return {
    ...result,
    pairs: result.pairs ?? [],
  };
}

function normalizePairs(result: TranslationResult) {
  return result.pairs ?? [];
}

/** 仅译文：优先 full_text，否则拼接句对译文；绝不使用 ocr_text（那是原文 OCR）。 */
export function getTranslationFullText(result: TranslationResult): string {
  if (result.full_text?.trim()) {
    return result.full_text.trim();
  }
  const targets = normalizePairs(result)
    .map((p) => p.target?.trim())
    .filter(Boolean);
  if (targets.length > 0) {
    return targets.join("\n\n");
  }
  return "";
}

/** 双语对照：优先句对；无句对时退回仅译文（避免展示 OCR 原文）。 */
export function getTranslationBilingualText(result: TranslationResult): string {
  const pairs = normalizePairs(result).filter(
    (p) => p.source?.trim() || p.target?.trim()
  );
  if (pairs.length > 0) {
    return pairs
      .map((p) => `${p.source.trim()}\n${p.target?.trim() ?? ""}`.trim())
      .join("\n\n");
  }
  const fallback = getTranslationFullText(result);
  return fallback;
}

export function formatTranslationResult(
  result: TranslationResult,
  mode: TranslateDisplayMode
): string {
  if (mode === "bilingual") {
    const bilingual = getTranslationBilingualText(result);
    if (bilingual) return bilingual;
    return "Could not build bilingual output. Retry or switch to Translation only.";
  }
  return getTranslationFullText(result);
}

export function formatVideoCueText(
  result: VideoTranslationResult,
  index: number,
  mode: TranslateDisplayMode
): string {
  const cue = result.cues[index];
  if (!cue) return "";
  if (mode === "bilingual") {
    const zh = cue.translation?.trim() ?? "";
    if (zh) return `${cue.text.trim()}\n${zh}`;
    return cue.text.trim();
  }
  return cue.translation?.trim() || cue.text.trim();
}

export function formatVideoResultText(
  result: VideoTranslationResult,
  mode: TranslateDisplayMode
): string {
  return result.cues
    .map((_, i) => formatVideoCueText(result, i, mode))
    .filter(Boolean)
    .join("\n\n");
}
