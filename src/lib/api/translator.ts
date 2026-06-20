import { apiFetch, apiUpload } from "@/lib/api/client";
import { getAuthHeaders } from "@/lib/api/auth-fetch";
import { normalizeTranslationResult } from "@/lib/translator/format-result";
import type {
  TranslationResult,
  TranslatorHealth,
  VideoTranslationResult,
} from "@/lib/api/types";

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

async function authUpload<T>(path: string, formData: FormData): Promise<T> {
  const authHeaders = await getAuthHeaders();
  return apiUpload<T>(path, formData, authHeaders);
}

export async function getTranslatorHealth(): Promise<TranslatorHealth> {
  return authFetch<TranslatorHealth>("/api/translator/health");
}

export async function translateText(params: {
  text: string;
  mode?: string;
  domain?: string;
  export_format?: string;
}): Promise<TranslationResult> {
  const data = await authFetch<TranslationResult>("/api/translator/text", {
    method: "POST",
    body: JSON.stringify(params),
  });
  return normalizeTranslationResult(data);
}

export async function translateImage(
  file: File,
  params?: {
    mode?: string;
    domain?: string;
    export_format?: string;
  }
): Promise<TranslationResult> {
  const formData = new FormData();
  formData.append("file", file);
  if (params?.mode) formData.append("mode", params.mode);
  if (params?.domain) formData.append("domain", params.domain);
  if (params?.export_format) formData.append("export_format", params.export_format);
  return normalizeTranslationResult(
    await authUpload<TranslationResult>("/api/translator/image", formData)
  );
}

export async function translateDocument(
  file: File,
  params?: {
    mode?: string;
    domain?: string;
    export_format?: string;
  }
): Promise<TranslationResult> {
  const formData = new FormData();
  formData.append("file", file);
  if (params?.mode) formData.append("mode", params.mode);
  if (params?.domain) formData.append("domain", params.domain);
  if (params?.export_format) formData.append("export_format", params.export_format);
  return normalizeTranslationResult(
    await authUpload<TranslationResult>("/api/translator/document", formData)
  );
}

export async function translateVideo(
  file: File,
  params?: {
    subtitle_mode?: string;
    domain?: string;
    export_format?: string;
  }
): Promise<VideoTranslationResult> {
  const formData = new FormData();
  formData.append("file", file);
  if (params?.subtitle_mode) formData.append("subtitle_mode", params.subtitle_mode);
  if (params?.domain) formData.append("domain", params.domain);
  if (params?.export_format) formData.append("export_format", params.export_format);
  return authUpload<VideoTranslationResult>("/api/translator/video", formData);
}

export async function translateFromNotebook(params: {
  question_id: number;
  mode?: string;
  domain?: string;
  export_format?: string;
  subtitle_mode?: string;
}): Promise<TranslationResult | VideoTranslationResult> {
  const data = await authFetch<TranslationResult | VideoTranslationResult>(
    "/api/translator/from-notebook",
    {
      method: "POST",
      body: JSON.stringify(params),
    }
  );
  if ("cues" in data) {
    return data;
  }
  return normalizeTranslationResult(data);
}

export async function saveTranslationToNotebook(params: {
  question_id: number;
  content: string;
  append?: boolean;
}): Promise<{ question_id: number; notes: string }> {
  return authFetch<{ question_id: number; notes: string }>(
    "/api/translator/save-to-notebook",
    {
      method: "POST",
      body: JSON.stringify(params),
    }
  );
}
