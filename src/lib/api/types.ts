/** 统一 API 响应格式 */
export type ApiResponse<T> = {
  success: boolean;
  data: T;
  message: string;
};

export type ChatSession = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ChatMessage = {
  id: number;
  role: "user" | "assistant" | "system";
  content: string;
  image_path: string | null;
  created_at: string;
};

export type WrongQuestionCategory = {
  id: number;
  name: string;
  created_at: string;
  question_count: number;
};

export type WrongQuestion = {
  id: number;
  category_id: number;
  category_name: string;
  title: string;
  image_path: string;
  notes: string;
  ai_analysis: string | null;
  created_at: string;
};

export type StartChatFromQuestionResult = {
  session_id: string;
  title: string;
  image_path: string;
  initial_message: string;
};
