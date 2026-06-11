import { apiFetch, apiUpload } from "@/lib/api/client";
import type {
  StartChatFromQuestionResult,
  WrongQuestion,
  WrongQuestionCategory,
} from "@/lib/api/types";

export async function listCategories(): Promise<WrongQuestionCategory[]> {
  return apiFetch<WrongQuestionCategory[]>("/api/wrong-questions/categories");
}

export async function createCategory(
  name: string
): Promise<WrongQuestionCategory> {
  return apiFetch<WrongQuestionCategory>("/api/wrong-questions/categories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export async function listWrongQuestions(
  categoryId?: number | null
): Promise<WrongQuestion[]> {
  const q =
    categoryId != null ? `?category_id=${categoryId}` : "";
  return apiFetch<WrongQuestion[]>(`/api/wrong-questions${q}`);
}

export async function getWrongQuestion(
  id: number
): Promise<WrongQuestion> {
  return apiFetch<WrongQuestion>(`/api/wrong-questions/${id}`);
}

export async function updateWrongQuestion(
  id: number,
  data: { title?: string; notes?: string; category_id?: number }
): Promise<WrongQuestion> {
  return apiFetch<WrongQuestion>(`/api/wrong-questions/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function deleteWrongQuestion(id: number): Promise<void> {
  await apiFetch<null>(`/api/wrong-questions/${id}`, { method: "DELETE" });
}

export async function uploadWrongQuestion(params: {
  file: File;
  categoryId?: number;
  categoryName?: string;
  title?: string;
  notes?: string;
}): Promise<WrongQuestion> {
  const form = new FormData();
  form.append("file", params.file);
  if (params.categoryId != null) {
    form.append("category_id", String(params.categoryId));
  }
  if (params.categoryName) form.append("category_name", params.categoryName);
  if (params.title) form.append("title", params.title);
  if (params.notes) form.append("notes", params.notes);
  return apiUpload<WrongQuestion>("/api/wrong-questions/upload", form);
}

export async function analyzeWrongQuestion(
  questionId: number
): Promise<{ ai_analysis: string }> {
  return apiFetch<{ ai_analysis: string }>("/api/wrong-questions/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_id: questionId }),
  });
}

export async function startChatFromQuestion(
  questionId: number
): Promise<StartChatFromQuestionResult> {
  return apiFetch<StartChatFromQuestionResult>(
    `/api/wrong-questions/${questionId}/start-chat`,
    { method: "POST" }
  );
}
