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
  /** 用户消息展示文案（不含 OCR），由后端计算 */
  display_content?: string | null;
  image_path: string | null;
  /** 本地上传图片的临时预览（仅前端会话内展示，不落盘） */
  local_preview?: string | null;
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
