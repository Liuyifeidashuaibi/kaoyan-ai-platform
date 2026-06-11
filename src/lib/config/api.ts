/**
 * FastAPI 后端地址。
 * - 未设置时走同源 Next.js rewrite（本地 / Vercel 均可用）
 * - 设置 NEXT_PUBLIC_API_URL 时直连后端（适合 SSE 长连接）
 */
export function getApiBaseUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (explicit) return explicit.replace(/\/$/, "");
  if (typeof window !== "undefined") return "";
  return (
    process.env.BACKEND_URL?.trim().replace(/\/$/, "") ||
    "http://127.0.0.1:8000"
  );
}

export const API_BASE_URL = getApiBaseUrl();

/** 将后端返回的相对路径转为可访问的完整 URL */
export function resolveUploadUrl(path: string | null | undefined): string {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const normalized = path.replace(/^\//, "");
  const base =
    getApiBaseUrl() ||
    (typeof window !== "undefined"
      ? window.location.origin
      : "http://localhost:3000");
  return `${base}/${normalized}`;
}
