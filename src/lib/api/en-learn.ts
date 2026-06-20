import { apiFetch, apiUpload } from "@/lib/api/client";
import { getAuthHeaders } from "@/lib/api/auth-fetch";

export type ErrorItem = {
  word: string;
  correction: string;
  start: number;
  end: number;
};

export type EnLearnTranslateResult = {
  original_text: string;
  corrected_text: string;
  error_list: ErrorItem[];
  mode: string;
  pairs: { source: string; target: string }[];
  full_text: string | null;
  chinese_text: string | null;
  ocr_text?: string;
  kind?: string;
};

async function authFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const authHeaders = await getAuthHeaders();
  return apiFetch<T>(path, {
    ...init,
    headers: {
      ...authHeaders,
      ...(init?.headers ?? {}),
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
    },
  });
}

export async function enLearnTranslateText(params: {
  text: string;
  mode?: string;
}): Promise<EnLearnTranslateResult> {
  return authFetch<EnLearnTranslateResult>("/api/en-learn/translate/text", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function enLearnTranslateImage(
  file: File,
  mode = "bilingual"
): Promise<EnLearnTranslateResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("mode", mode);
  const authHeaders = await getAuthHeaders();
  return apiUpload<EnLearnTranslateResult>(
    "/api/en-learn/translate/image",
    formData,
    authHeaders
  );
}
