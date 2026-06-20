import { apiFetch } from "@/lib/api/client";
import { getAuthHeaders } from "@/lib/api/auth-fetch";

export type UserSettings = {
  translation_download_email: string | null;
  email_delivery_configured: boolean;
};

async function authFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const authHeaders = await getAuthHeaders();
  return apiFetch<T>(path, {
    ...init,
    headers: {
      ...authHeaders,
      ...(init?.headers ?? {}),
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
    },
  });
}

export async function getUserSettings(): Promise<UserSettings> {
  return authFetch<UserSettings>("/api/settings");
}

export async function updateUserSettings(params: {
  translation_download_email?: string | null;
}): Promise<UserSettings> {
  return authFetch<UserSettings>("/api/settings", {
    method: "PATCH",
    body: JSON.stringify(params),
  });
}

export type ExportFormat = "txt" | "docx" | "pdf";

export async function emailTranslationExport(params: {
  content: string;
  export_format: ExportFormat;
  title?: string;
}): Promise<{ email: string; format: string; filename: string }> {
  return authFetch<{ email: string; format: string; filename: string }>(
    "/api/translator/email-export",
    {
      method: "POST",
      body: JSON.stringify(params),
    }
  );
}
