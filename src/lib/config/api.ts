/**
 * FastAPI 后端地址。
 * - 浏览器优先读 NEXT_PUBLIC_API_URL；否则拉 /api/runtime-config（BACKEND_URL）
 * - 均未配置时走同源 Next.js rewrite
 */
let runtimeBaseUrl: string | null = null;
let runtimeInitPromise: Promise<void> | null = null;

function readBuildTimeApiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/$/, "") || "";
}

export function getApiBaseUrl(): string {
  const buildTime = readBuildTimeApiUrl();
  if (buildTime) return buildTime;
  if (typeof window !== "undefined" && runtimeBaseUrl !== null) {
    return runtimeBaseUrl;
  }
  if (typeof window !== "undefined") return "";
  return (
    process.env.BACKEND_URL?.trim().replace(/\/$/, "") ||
    "http://127.0.0.1:8000"
  );
}

/** 浏览器端：从 Next.js 读取 BACKEND_URL（Vercel 环境变量，无需 rebuild） */
export async function initApiBaseUrl(): Promise<void> {
  if (typeof window === "undefined") return;
  if (readBuildTimeApiUrl()) return;
  if (runtimeBaseUrl !== null) return;
  if (!runtimeInitPromise) {
    runtimeInitPromise = (async () => {
      try {
        const res = await fetch("/api/runtime-config", { cache: "no-store" });
        if (!res.ok) throw new Error(String(res.status));
        const data = (await res.json()) as { apiBaseUrl?: string };
        runtimeBaseUrl = (data.apiBaseUrl ?? "").replace(/\/$/, "");
      } catch {
        runtimeBaseUrl = "";
      }
    })();
  }
  await runtimeInitPromise;
}

export async function ensureApiBaseUrl(): Promise<string> {
  await initApiBaseUrl();
  return getApiBaseUrl();
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
