import { apiFetch, apiUpload } from "@/lib/api/client";
import { getApiBaseUrl } from "@/lib/config/api";
import type { ChatMessage, ChatSession } from "@/lib/api/types";

export async function createChatSession(title = "新对话"): Promise<ChatSession> {
  return apiFetch<ChatSession>("/api/chat/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
}

export async function listChatSessions(
  keyword = ""
): Promise<ChatSession[]> {
  const q = keyword ? `?keyword=${encodeURIComponent(keyword)}` : "";
  return apiFetch<ChatSession[]>(`/api/chat/sessions${q}`);
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await apiFetch<null>(`/api/chat/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

export async function getChatMessages(
  sessionId: string
): Promise<ChatMessage[]> {
  return apiFetch<ChatMessage[]>(`/api/chat/sessions/${sessionId}/messages`);
}

export async function uploadChatImage(
  file: File
): Promise<{ image_path: string; image_url?: string | null }> {
  const form = new FormData();
  form.append("file", file);
  return apiUpload<{ image_path: string; image_url?: string | null }>(
    "/api/chat/upload-image",
    form
  );
}

export type StreamChatOptions = {
  sessionId: string;
  content: string;
  imagePath?: string | null;
  /** 用户消息已存在（如错题本一键追问）时设为 true */
  skipUserSave?: boolean;
  onToken: (token: string) => void;
  signal?: AbortSignal;
};

/**
 * SSE 流式发送消息，逐 token 回调 onToken。
 */
export async function streamChatMessage({
  sessionId,
  content,
  imagePath,
  skipUserSave,
  onToken,
  signal,
}: StreamChatOptions): Promise<void> {
  const form = new FormData();
  form.append("session_id", sessionId);
  form.append("content", content);
  if (imagePath) form.append("image_path", imagePath);
  if (skipUserSave) form.append("skip_user_save", "true");

  const res = await fetch(`${getApiBaseUrl()}/api/chat/send/stream`, {
    method: "POST",
    body: form,
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`流式请求失败 (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6).trim();
      if (!payload) continue;

      try {
        const data = JSON.parse(payload) as {
          token?: string;
          done?: boolean;
          error?: string;
        };
        if (data.error) throw new Error(data.error);
        if (data.token) onToken(data.token);
      } catch (e) {
        if (e instanceof SyntaxError) continue;
        throw e;
      }
    }
  }
}
