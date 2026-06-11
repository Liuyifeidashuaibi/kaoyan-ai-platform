import { ensureApiBaseUrl } from "@/lib/config/api";
import type { ApiResponse } from "@/lib/api/types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** 通用 JSON 请求封装 */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const base = await ensureApiBaseUrl();
  const res = await fetch(`${base}${path}`, init);
  const json = (await res.json()) as ApiResponse<T>;

  if (!res.ok || !json.success) {
    throw new ApiError(json.message || `请求失败 (${res.status})`, res.status);
  }

  return json.data;
}

/** multipart 上传（不经过统一 JSON 包装的路径用 raw fetch） */
export async function apiUpload<T>(
  path: string,
  formData: FormData
): Promise<T> {
  const base = await ensureApiBaseUrl();
  const res = await fetch(`${base}${path}`, {
    method: "POST",
    body: formData,
  });
  const json = (await res.json()) as ApiResponse<T>;

  if (!res.ok || !json.success) {
    throw new ApiError(json.message || `上传失败 (${res.status})`, res.status);
  }

  return json.data;
}
