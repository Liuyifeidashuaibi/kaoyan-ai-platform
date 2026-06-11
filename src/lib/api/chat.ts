import { apiFetch } from "@/lib/api/client";

import { ensureApiBaseUrl } from "@/lib/config/api";

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



export type StreamChatOptions = {

  sessionId: string;

  content: string;

  /** 本地上传图片，随消息一并发送（内存 Base64，不落盘） */

  imageFile?: File | null;

  /** 错题本追问等已落盘路径 */

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

  imageFile,

  imagePath,

  skipUserSave,

  onToken,

  signal,

}: StreamChatOptions): Promise<void> {

  const form = new FormData();
  form.append("session_id", sessionId);
  form.append("content", content);

  if (imageFile) {
    form.append("image_file", imageFile, imageFile.name || "image.jpg");
  }

  if (imagePath) form.append("image_path", imagePath);

  if (skipUserSave) form.append("skip_user_save", "true");



  const base = await ensureApiBaseUrl();
  const res = await fetch(`${base}/api/chat/send/stream`, {

    method: "POST",

    body: form,

    signal,

  });



  if (!res.ok) {

    let message = `流式请求失败 (${res.status})`;

    try {

      const body = (await res.json()) as { message?: string };

      if (body.message) message = body.message;

    } catch {

      /* ignore */

    }

    throw new Error(message);

  }



  if (!res.body) {

    throw new Error("流式响应为空");

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


