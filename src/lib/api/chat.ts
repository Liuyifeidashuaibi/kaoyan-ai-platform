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



/** 录音转文字（仅 ASR，结果填入输入框） */
export async function transcribeAudio(audio: Blob | File): Promise<string> {
  const base = await ensureApiBaseUrl();
  const form = new FormData();
  const name = audio instanceof File ? audio.name : "recording.wav";
  form.append("audio_file", audio, name);

  const res = await fetch(`${base}/api/chat/transcribe`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    let message = `语音识别失败 (${res.status})`;
    try {
      const body = (await res.json()) as { message?: string };
      if (body.message) message = body.message;
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }

  const body = (await res.json()) as { data?: { text?: string }; message?: string };
  const text = body.data?.text?.trim();
  if (!text) throw new Error(body.message || "未识别到语音内容");
  return text;
}

export type StreamChatDonePayload = {
  ttsAudioBase64?: string;
};

export type StreamChatOptions = {
  sessionId: string;
  content: string;
  imageFile?: File | null;
  audioFile?: Blob | File | null;
  imagePath?: string | null;
  skipUserSave?: boolean;
  /** 开启后服务端合成语音，在 onDone 中返回 base64 */
  enableTts?: boolean;
  onToken: (token: string) => void;
  onDone?: (payload: StreamChatDonePayload) => void;
  signal?: AbortSignal;
};



/**

 * SSE 流式发送消息，逐 token 回调 onToken。

 */

export async function streamChatMessage({
  sessionId,
  content,
  imageFile,
  audioFile,
  imagePath,
  skipUserSave,
  enableTts,
  onToken,
  onDone,
  signal,
}: StreamChatOptions): Promise<void> {
  const form = new FormData();
  form.append("session_id", sessionId);
  form.append("content", content);

  if (imageFile) {
    form.append("image_file", imageFile, imageFile.name || "image.jpg");
  }

  if (audioFile) {
    const name =
      audioFile instanceof File ? audioFile.name : "recording.wav";
    form.append("audio_file", audioFile, name);
  }

  if (imagePath) form.append("image_path", imagePath);
  if (skipUserSave) form.append("skip_user_save", "true");
  if (enableTts) form.append("enable_tts", "true");



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
          tts_audio_base64?: string;
        };

        if (data.error) throw new Error(data.error);
        if (data.token) onToken(data.token);
        if (data.done) {
          onDone?.({
            ttsAudioBase64: data.tts_audio_base64,
          });
        }

      } catch (e) {

        if (e instanceof SyntaxError) continue;

        throw e;

      }

    }

  }

}


