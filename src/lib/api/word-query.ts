import { apiFetch } from "@/lib/api/client";
import { getAuthHeaders } from "@/lib/api/auth-fetch";

export type WordBrief = {
  word: string;
  phonetic: string | null;
  pos: string | null;
  gloss: string;
  source: string;
};

export type WordDetail = WordBrief & {
  translation: string | null;
  definition: string | null;
  tag: string | null;
  collins: number | null;
  oxford: number | null;
  exchange: string | null;
  detail: string | null;
  kaoyan_gloss: string | null;
  kaoyan_phrases: string[];
};

export async function queryWord(
  word: string,
  mode: "hover" | "detail" = "hover"
): Promise<WordBrief | WordDetail> {
  const authHeaders = await getAuthHeaders();
  const q = new URLSearchParams({ word, mode });
  const timeoutMs = mode === "hover" ? 2500 : 120_000;
  return apiFetch<WordBrief | WordDetail>(`/api/word-query?${q}`, {
    headers: authHeaders,
    signal: AbortSignal.timeout(timeoutMs),
  });
}
