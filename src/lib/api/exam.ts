/**
 * 试卷解析 API 客户端
 */

import { rateLimitedApiFetch } from "@/lib/api/rate_limited_client";
import { getAuthHeaders } from "@/lib/api/auth-fetch";
import type {
  ExamPaper,
  ExamUploadResponse,
  ExamVocabulary,
} from "@/lib/api/types";

async function examFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = await getAuthHeaders();
  return rateLimitedApiFetch<T>(path, {
    ...init,
    headers: { ...headers, ...(init?.headers as Record<string, string>) },
  });
}

/**
 * 上传试卷图片并启动解析任务。
 * 返回 paper_id 和 task_id，前端可通过 task_id 轮询进度。
 */
export async function uploadExam(
  file: File,
  subject: "english" | "math",
  opts?: { sessionId?: string; title?: string }
): Promise<ExamUploadResponse> {
  const fd = new FormData();
  fd.append("image_file", file);
  fd.append("subject", subject);
  fd.append("session_id", opts?.sessionId ?? "");
  fd.append("title", opts?.title ?? file.name);

  const headers = await getAuthHeaders();
  return rateLimitedApiFetch<ExamUploadResponse>("/api/exam/upload", {
    method: "POST",
    body: fd,
    headers,
  });
}

/**
 * 获取试卷详情（含解析结果）。
 */
export async function fetchExamPaper(paperId: number): Promise<ExamPaper> {
  return examFetch<ExamPaper>(`/api/exam/${paperId}`);
}

/**
 * 获取试卷结构化题目列表。
 */
export async function fetchExamQuestions(paperId: number): Promise<{
  paper_id: number;
  subject: string;
  total_questions: number;
  sections: Array<{ type: string; title: string; questions: unknown[] }>;
}> {
  return examFetch(`/api/exam/${paperId}/questions`);
}

/**
 * 对单题发起追问，返回 SSE ReadableStream。
 * 调用方需自行解析 SSE 事件流。
 */
export async function askExamQuestion(
  paperId: number,
  questionId: string,
  question: string,
  sessionId?: string
): Promise<Response> {
  const { ensureApiBaseUrl } = await import("@/lib/config/api");
  const base = await ensureApiBaseUrl();
  const headers = await getAuthHeaders();

  const res = await fetch(
    `${base}/api/exam/${paperId}/questions/${encodeURIComponent(questionId)}/ask`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ question, session_id: sessionId ?? null }),
    }
  );

  if (!res.ok) {
    throw new Error(`追问请求失败: ${res.status}`);
  }
  return res;
}

/**
 * 收藏题目到永久知识库 kaoyan_bank。
 */
export async function favoriteExamQuestions(
  paperId: number,
  questionIds: string[],
  subject?: string
): Promise<{ favorited: number }> {
  return examFetch(`/api/exam/${paperId}/favorite`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_ids: questionIds, subject }),
  });
}

/**
 * 导出英语试卷生词列表。
 */
export async function exportExamVocabulary(
  paperId: number
): Promise<{
  paper_id: number;
  vocabulary: ExamVocabulary[];
  total_words: number;
}> {
  return examFetch(`/api/exam/${paperId}/vocabulary/export`, {
    method: "POST",
  });
}

/**
 * 清理指定会话关联的所有临时试卷数据（含向量）。
 */
export async function cleanupExamSession(sessionId: string): Promise<{
  session_id: string;
  deleted_papers: number;
  deleted_vectors: number;
  message: string;
}> {
  return examFetch(`/api/exam/session/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
}

// ---------------------------------------------------------------------------
// RAG 科目隔离检索
// ---------------------------------------------------------------------------

export interface ExamRagResult {
  text: string;
  score: number;
  subject: string;
  year: string;
  source: string;
}

export interface ExamRagSearchResponse {
  query: string;
  subject_filter: string | null;
  results: ExamRagResult[];
  total: number;
}

/**
 * RAG 科目隔离检索：从 kaoyan_bank 知识库中检索相关题目。
 *
 * @param query 查询文本
 * @param subject 科目过滤 (english/math/空=全部)
 * @param topK 返回结果数
 */
export async function searchExamRag(
  query: string,
  subject?: string,
  topK: number = 5,
): Promise<ExamRagSearchResponse> {
  const formData = new FormData();
  formData.append("query", query);
  if (subject) formData.append("subject", subject);
  formData.append("top_k", String(topK));

  return examFetch("/api/exam/rag/search", {
    method: "POST",
    body: formData,
  });
}
