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

function readErrorMessage(
  json: Record<string, unknown>,
  status: number
): string {
  const message = json.message;
  if (typeof message === "string" && message.trim()) return message;
  const detail = json.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const nested = detail as Record<string, unknown>;
    if (typeof nested.message === "string" && nested.message.trim()) {
      return nested.message;
    }
  }
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) =>
        item && typeof item === "object" && "msg" in item
          ? String((item as { msg: unknown }).msg)
          : ""
      )
      .filter(Boolean);
    if (parts.length > 0) return parts.join("；");
  }
  return `请求失败 (${status})`;
}

/** 通用 JSON 请求封装 */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const base = await ensureApiBaseUrl();
  let res: Response;
  try {
    res = await fetch(`${base}${path}`, init);
  } catch (err) {
    const hint =
      base && base.startsWith("http")
        ? "请确认后端已启动，或移除 NEXT_PUBLIC_API_URL 走同源代理"
        : "请确认后端已启动（BACKEND_URL）";
    throw new ApiError(
      err instanceof Error && err.message === "Failed to fetch"
        ? `无法连接服务器，${hint}`
        : err instanceof Error
          ? err.message
          : "网络错误",
      0
    );
  }

  let json: ApiResponse<T> & { detail?: string };
  const contentType = res.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    const text = (await res.text()).trim();
    throw new ApiError(text || `请求失败 (${res.status})`, res.status);
  }
  try {
    json = (await res.json()) as ApiResponse<T> & { detail?: string };
  } catch {
    throw new ApiError(`响应解析失败 (${res.status})`, res.status);
  }

  if (!res.ok || !json.success) {
    throw new ApiError(readErrorMessage(json, res.status), res.status);
  }

  return json.data;
}

/** multipart 上传（不经过统一 JSON 包装的路径用 raw fetch） */
export async function apiUpload<T>(
  path: string,
  formData: FormData,
  headers?: HeadersInit
): Promise<T> {
  const base = await ensureApiBaseUrl();
  let res: Response;
  try {
    res = await fetch(`${base}${path}`, {
      method: "POST",
      body: formData,
      headers,
    });
  } catch (err) {
    throw new ApiError(
      err instanceof Error ? err.message : "上传失败：网络错误",
      0
    );
  }
  const contentType = res.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    const text = (await res.text()).trim();
    throw new ApiError(text || `上传失败 (${res.status})`, res.status);
  }
  let json: ApiResponse<T> & { detail?: string };
  try {
    json = (await res.json()) as ApiResponse<T> & { detail?: string };
  } catch {
    throw new ApiError(`上传响应解析失败 (${res.status})`, res.status);
  }

  if (!res.ok || !json.success) {
    throw new ApiError(readErrorMessage(json, res.status), res.status);
  }

  return json.data;
}
