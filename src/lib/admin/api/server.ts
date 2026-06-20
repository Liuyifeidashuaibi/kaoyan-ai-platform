import { createClient } from "@/lib/supabase/server";
import { getApiBaseUrl } from "@/lib/config/api";
import { shouldSkipAuthInDev } from "@/lib/auth/dev-auth";
import type { ApiResponse } from "@/lib/api/types";

async function adminAuthHeader(): Promise<HeadersInit> {
  if (shouldSkipAuthInDev()) {
    return { Authorization: "Bearer dev" };
  }
  try {
    const supabase = await createClient();
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) return { Authorization: `Bearer ${token}` };
  } catch {
    /* no session */
  }
  return {};
}

export type AdminFetchResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

export async function adminServerFetchResult<T>(path: string): Promise<AdminFetchResult<T>> {
  try {
    const base = getApiBaseUrl().replace(/\/$/, "") || "http://127.0.0.1:8000";
    const headers = await adminAuthHeader();
    const res = await fetch(`${base}${path}`, {
      headers,
      next: { revalidate: 30 },
      cache: "no-store",
    });
    if (!res.ok) {
      return { ok: false, error: `API ${res.status}` };
    }
    const json = (await res.json()) as ApiResponse<T>;
    if (!json.success) {
      return { ok: false, error: json.message || "请求失败" };
    }
    return { ok: true, data: json.data as T };
  } catch {
    return { ok: false, error: "无法连接后端服务" };
  }
}

export async function adminServerFetch<T>(path: string): Promise<T | null> {
  const result = await adminServerFetchResult<T>(path);
  return result.ok ? result.data : null;
}
