/**
 * Agent 工作台 API 封装 — 任务历史 / 模板管理 / 批量任务。
 *
 * 对应后端：
 *   GET  /api/chat/agent/tasks           任务列表
 *   GET  /api/chat/agent/tasks/{id}      任务详情（含每步工具调用）
 *   GET/POST/PUT/DELETE /api/agent/templates[/{id}]   模板 CRUD
 *   POST /api/agent/templates/ingest     上传模板文件向量化
 *   POST /api/agent/batch                提交批量任务
 *   GET  /api/agent/batch/{id}           轮询批量进度（复用 task_store）
 *
 * 沿用 rateLimitedApiFetch + getAuthHeaders 风格，不引入新组件。
 */

import { rateLimitedApiFetch } from "@/lib/api/rate_limited_client";
import { getAuthHeaders } from "@/lib/api/auth-fetch";

// ── 任务历史 ────────────────────────────────────────────

/** 任务列表项（轻量） */
export type AgentTaskSummary = {
  task_id: string;
  session_id: string;
  user_input: string;
  /** running / completed / failed */
  status: string;
  steps_count: number;
  started_at: string;
  success: boolean;
};

/** 任务详情中的单步工具调用 */
export type AgentTaskStep = {
  step_id: number;
  round_idx: number;
  tool_name: string;
  args: Record<string, unknown>;
  result: Record<string, unknown>;
  status: string;
  error: string;
  duration_ms: number;
  timestamp: string;
};

/** 任务详情中的生成文件 */
export type AgentTaskFile = {
  filename: string;
  file_url: string;
  file_path: string;
  file_size: number;
  format: string;
  title: string;
};

/** 任务详情（含步骤与文件） */
export type AgentTaskDetail = {
  task_id: string;
  session_id: string;
  user_input: string;
  /** running / completed / failed */
  status: string;
  steps: AgentTaskStep[];
  final_output: string;
  files_generated: AgentTaskFile[];
  started_at: string;
  finished_at: string;
  total_duration_ms: number;
  success: boolean;
  error: string;
};

export async function listAgentTasks(limit = 20): Promise<AgentTaskSummary[]> {
  return rateLimitedApiFetch<AgentTaskSummary[]>(
    `/api/chat/agent/tasks?limit=${limit}`
  );
}

export async function getAgentTaskDetail(
  taskId: string
): Promise<AgentTaskDetail> {
  return rateLimitedApiFetch<AgentTaskDetail>(
    `/api/chat/agent/tasks/${taskId}`
  );
}

// ── 模板管理 ────────────────────────────────────────────

export type AgentTemplate = {
  id: number;
  name: string;
  category: string;
  doc_type: string;
  description: string;
  style_rules: string;
  cover_format: string;
  validation_rules: string;
  source_text: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type TemplateUpsertInput = {
  name: string;
  category?: string;
  doc_type?: string;
  description?: string;
  style_rules?: Record<string, unknown>;
  cover_format?: Record<string, unknown>;
  validation_rules?: Record<string, unknown>;
  source_text?: string;
};

export async function listAgentTemplates(params?: {
  category?: string;
  doc_type?: string;
  active_only?: boolean;
}): Promise<AgentTemplate[]> {
  const qs = new URLSearchParams();
  if (params?.category) qs.set("category", params.category);
  if (params?.doc_type) qs.set("doc_type", params.doc_type);
  if (params?.active_only !== undefined) {
    qs.set("active_only", String(params.active_only));
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return rateLimitedApiFetch<AgentTemplate[]>(`/api/agent/templates${suffix}`);
}

export async function createAgentTemplate(
  input: TemplateUpsertInput
): Promise<AgentTemplate> {
  return rateLimitedApiFetch<AgentTemplate>("/api/agent/templates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function updateAgentTemplate(
  id: number,
  input: Partial<TemplateUpsertInput> & { is_active?: boolean }
): Promise<AgentTemplate> {
  return rateLimitedApiFetch<AgentTemplate>(`/api/agent/templates/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function deleteAgentTemplate(id: number): Promise<void> {
  await rateLimitedApiFetch<{ message: string }>(
    `/api/agent/templates/${id}`,
    { method: "DELETE" }
  );
}

/** 上传模板文件向量化入库 */
export async function ingestTemplateFile(
  file: File,
  name: string,
  category = "general",
  doc_type = "pdf"
): Promise<AgentTemplate> {
  const headers = await getAuthHeaders();
  const form = new FormData();
  form.append("file", file, file.name);
  form.append("name", name);
  form.append("category", category);
  form.append("doc_type", doc_type);

  const base = await import("@/lib/config/api").then((m) =>
    m.ensureApiBaseUrl()
  );
  const res = await fetch(`${base}/api/agent/templates/ingest`, {
    method: "POST",
    body: form,
    headers,
  });

  const json = (await res.json()) as {
    success?: boolean;
    data?: AgentTemplate;
    message?: string;
  };
  if (!res.ok || !json.success) {
    throw new Error(json.message || `模板入库失败 (${res.status})`);
  }
  return json.data as AgentTemplate;
}

// ── 批量任务 ────────────────────────────────────────────

/** 单项任务规范（文件 + 指令） */
export type BatchItemSpec = {
  instruction: string;
  /** 对应上传文件列表索引，缺省表示该项无文件 */
  file_index?: number;
};

export type BatchSubmitResponse = {
  task_id: string;
  status: string;
  item_count: number;
};

/** 批量结果中的单项 */
export type BatchResultItem = {
  index: number;
  instruction: string;
  file_name: string | null;
  ok: boolean;
  task_id?: string;
  final_output?: string;
  files?: Array<{ file_url?: string; filename?: string; title?: string }>;
  error?: string;
};

export type BatchResultPayload = {
  total: number;
  success: number;
  failed: number;
  items: BatchResultItem[];
};

/**
 * 提交批量任务。
 * 前端将每项指令与对应文件按 file_index 关联，后端保存文件后提交 Celery。
 */
export async function submitAgentBatch(
  files: File[],
  items: BatchItemSpec[]
): Promise<BatchSubmitResponse> {
  const headers = await getAuthHeaders();
  const form = new FormData();
  files.forEach((f) => form.append("files", f, f.name));
  form.append("instructions", JSON.stringify(items));

  const base = await import("@/lib/config/api").then((m) =>
    m.ensureApiBaseUrl()
  );
  const res = await fetch(`${base}/api/agent/batch`, {
    method: "POST",
    body: form,
    headers,
  });

  const json = (await res.json()) as {
    success?: boolean;
    data?: BatchSubmitResponse;
    message?: string;
  };
  if (!res.ok || !json.success) {
    throw new Error(json.message || `批量提交失败 (${res.status})`);
  }
  return json.data as BatchSubmitResponse;
}

export type BatchStatusRecord = {
  id: string;
  type: string;
  status: "pending" | "running" | "done" | "failed";
  progress: number;
  status_label: string;
  message: string;
  result?: BatchResultPayload | null;
  error?: string | null;
  created_at?: string;
  updated_at?: string;
};

/** 轮询批量任务进度（复用 task_store，需带鉴权头） */
export async function fetchAgentBatchStatus(
  taskId: string
): Promise<BatchStatusRecord> {
  const headers = await getAuthHeaders();
  return rateLimitedApiFetch<BatchStatusRecord>(
    `/api/agent/batch/${taskId}`,
    { headers }
  );
}
