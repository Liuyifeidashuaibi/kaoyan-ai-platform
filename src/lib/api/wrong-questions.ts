import { apiFetch, apiUpload } from "@/lib/api/client";
import { getAuthHeaders } from "@/lib/api/auth-fetch";
import type {
  MaterialFileType,
  StartChatFromQuestionResult,
  WrongQuestion,
  WrongQuestionCategory,
} from "@/lib/api/types";

async function authFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const authHeaders = await getAuthHeaders();
  return apiFetch<T>(path, {
    ...init,
    headers: {
      ...authHeaders,
      ...(init?.headers ?? {}),
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
    },
  });
}

async function authUpload<T>(path: string, formData: FormData): Promise<T> {
  const authHeaders = await getAuthHeaders();
  return apiUpload<T>(path, formData, authHeaders);
}

export async function listCategories(): Promise<WrongQuestionCategory[]> {
  return authFetch<WrongQuestionCategory[]>("/api/wrong-questions/categories");
}

export async function createCategory(
  name: string
): Promise<WrongQuestionCategory> {
  return authFetch<WrongQuestionCategory>("/api/wrong-questions/categories", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function listWrongQuestions(
  categoryId?: number | null,
  fileType?: MaterialFileType | null
): Promise<WrongQuestion[]> {
  const params = new URLSearchParams();
  if (categoryId != null) params.set("category_id", String(categoryId));
  if (fileType) params.set("file_type", fileType);
  const q = params.toString() ? `?${params.toString()}` : "";
  return authFetch<WrongQuestion[]>(`/api/wrong-questions${q}`);
}

export async function listPublicMaterials(
  userId: string
): Promise<WrongQuestion[]> {
  return apiFetch<WrongQuestion[]>(
    `/api/wrong-questions/public?user_id=${encodeURIComponent(userId)}`
  );
}

export async function getWrongQuestion(
  id: number
): Promise<WrongQuestion> {
  return authFetch<WrongQuestion>(`/api/wrong-questions/${id}`);
}

export async function updateWrongQuestion(
  id: number,
  data: {
    title?: string;
    notes?: string;
    category_id?: number;
    is_public?: boolean;
  }
): Promise<WrongQuestion> {
  return authFetch<WrongQuestion>(`/api/wrong-questions/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteWrongQuestion(id: number): Promise<void> {
  await authFetch<null>(`/api/wrong-questions/${id}`, { method: "DELETE" });
}

export async function uploadWrongQuestion(params: {
  file: File;
  categoryId?: number;
  categoryName?: string;
  title?: string;
  notes?: string;
  isPublic?: boolean;
}): Promise<WrongQuestion> {
  const form = new FormData();
  form.append("file", params.file);
  if (params.categoryId != null) {
    form.append("category_id", String(params.categoryId));
  }
  if (params.categoryName) form.append("category_name", params.categoryName);
  if (params.title) form.append("title", params.title);
  if (params.notes) form.append("notes", params.notes);
  if (params.isPublic) form.append("is_public", "true");
  return authUpload<WrongQuestion>("/api/wrong-questions/upload", form);
}

export async function analyzeWrongQuestion(
  questionId: number
): Promise<{ ai_analysis: string }> {
  return authFetch<{ ai_analysis: string }>("/api/wrong-questions/analyze", {
    method: "POST",
    body: JSON.stringify({ question_id: questionId }),
  });
}

export async function startChatFromQuestion(
  questionId: number
): Promise<StartChatFromQuestionResult> {
  return authFetch<StartChatFromQuestionResult>(
    `/api/wrong-questions/${questionId}/start-chat`,
    { method: "POST" }
  );
}
