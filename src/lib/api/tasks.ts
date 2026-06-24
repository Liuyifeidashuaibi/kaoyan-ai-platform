/**
 * 异步任务 API — 与 chat/translator 等原有模块独立。
 */

import { rateLimitedApiFetch } from "@/lib/api/rate_limited_client";
import { getAuthHeaders } from "@/lib/api/auth-fetch";

export type TaskStatus = "pending" | "running" | "done" | "failed";

export interface AsyncTaskRecord {
  id: string;
  type: string;
  status: TaskStatus;
  progress: number;
  status_label: string;
  message: string;
  result?: unknown;
  error?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface MembershipQuota {
  user_id: string;
  tier: string;
  translate_used: number;
  translate_limit: number;
  chat_used: number;
  chat_limit: number;
}

async function tasksFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = await getAuthHeaders();
  return rateLimitedApiFetch<T>(path, {
    ...init,
    headers: { ...headers, ...(init?.headers as Record<string, string>) },
  });
}

async function tasksUpload<T>(
  path: string,
  formData: FormData
): Promise<T> {
  const headers = await getAuthHeaders();
  return rateLimitedApiFetch<T>(path, {
    method: "POST",
    body: formData,
    headers,
  });
}

export async function fetchTasksHealth() {
  return rateLimitedApiFetch<{
    redis_enabled: boolean;
    redis_url_configured: boolean;
    celery_broker: string;
    celery_beat_enabled: boolean;
  }>("/api/tasks/health");
}

export async function fetchTaskStatus(taskId: string) {
  return tasksFetch<AsyncTaskRecord>(`/api/tasks/${taskId}`);
}

export async function fetchMyTasks(limit = 20) {
  return tasksFetch<AsyncTaskRecord[]>(`/api/tasks?limit=${limit}`);
}

export async function fetchMembershipQuota() {
  return tasksFetch<MembershipQuota>("/api/tasks/quota");
}

export async function submitPdfParse(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  return tasksUpload<{ task_id: string; status: string }>(
    "/api/tasks/pdf/parse",
    fd
  );
}

export async function submitBatchOcr(files: File[]) {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  return tasksUpload<{ task_id: string; status: string; image_count: number }>(
    "/api/tasks/ocr/batch",
    fd
  );
}

export async function submitVectorIngest(source: "public" | "school" | "all" = "public", force = false) {
  const fd = new FormData();
  fd.append("source", source);
  fd.append("force", String(force));
  return tasksUpload<{ task_id: string; status: string }>(
    "/api/tasks/rag/ingest",
    fd
  );
}

export async function submitScoreCrawler() {
  return tasksFetch<{ task_id: string; status: string }>(
    "/api/tasks/crawler/scores",
    { method: "POST" }
  );
}
