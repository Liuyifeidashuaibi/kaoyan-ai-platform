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

export type MaterialFileType =
  | "image"
  | "video"
  | "document"
  | "audio"
  | "other";

export type WrongQuestion = {
  id: number;
  category_id: number;
  category_name: string;
  title: string;
  /** @deprecated 兼容旧字段，与 file_path 相同 */
  image_path: string;
  file_path: string;
  file_type: MaterialFileType;
  original_filename?: string | null;
  notes: string;
  ai_analysis: string | null;
  is_public: boolean;
  created_at: string;
};

export type CommunityUser = {
  id: string;
  display_id: string | null;
  nickname: string | null;
  avatar_url: string | null;
  subject_category: string | null;
  created_at?: string;
  following_count?: number;
  follower_count?: number;
  is_following?: boolean;
  is_self?: boolean;
  followed_at?: string;
};

export type CommunityAttachment = {
  url: string;
  name: string;
  mime_type: string;
};

export type CommunityPost = {
  id: string;
  author_id: string;
  post_type: "experience" | "material";
  subject_category: string;
  grade: string | null;
  university_id: string | null;
  university_name: string | null;
  title: string;
  content: string;
  attachments: CommunityAttachment[];
  view_count: number;
  favorite_count: number;
  comment_count: number;
  hot_score?: number;
  is_hidden: boolean;
  created_at: string;
  updated_at: string;
  author: CommunityUser;
  is_favorited?: boolean;
};

export type CommunityComment = {
  id: string;
  post_id: string;
  author_id: string;
  parent_id: string | null;
  content: string;
  created_at: string;
  author: CommunityUser;
};

export type PaginatedPosts = {
  items: CommunityPost[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
};

export type CommunitySearchResult =
  | { kind: "user"; user_id: string; display_id: string | null }
  | { kind: "subject"; subject_category: string }
  | { kind: "posts"; posts: CommunityPost[] };

export type TranslationMode = "full" | "bilingual";
export type TranslationDomain = "textbook" | "paper" | "technical";
export type SubtitleOutputMode = "original" | "translated" | "bilingual";

export type SentencePair = {
  source: string;
  target: string;
};

export type TranslationResult = {
  mode: TranslationMode;
  full_text: string | null;
  pairs: SentencePair[];
  source_name: string;
  kind: "text" | "image" | "document" | "video";
  ocr_text?: string | null;
  exported_content?: string | null;
  export_format?: string | null;
  notebook?: {
    question_id: number;
    title: string;
    file_type: string;
  };
};

export type SubtitleCue = {
  index: number;
  start: number;
  end: number;
  text: string;
  translation: string | null;
};

export type VideoTranslationResult = {
  source_name: string;
  detected_language: string | null;
  mode: SubtitleOutputMode;
  cues: SubtitleCue[];
  exported_content?: string | null;
  export_format?: string | null;
  notebook?: {
    question_id: number;
    title: string;
    file_type: string;
  };
};

export type TranslatorHealth = {
  available: boolean;
  configured: boolean;
  status?: string;
  model?: string;
  main_model?: string;
  draft_model?: string;
  qwen_model?: string;
  ollama_base_url?: string;
  whisper_model?: string;
  whisper_compute?: string;
};
