import { rateLimitedApiFetch, rateLimitedApiUpload } from "@/lib/api/rate_limited_client";

import { ensureApiBaseUrl } from "@/lib/config/api";

import type { AgentFile, AgentStep, ChatMessage, ChatSession } from "@/lib/api/types";



export async function createChatSession(title = "新对话"): Promise<ChatSession> {
  return rateLimitedApiFetch<ChatSession>("/api/chat/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
}



export async function listChatSessions(
  keyword = ""
): Promise<ChatSession[]> {
  const q = keyword ? `?keyword=${encodeURIComponent(keyword)}` : "";
  return rateLimitedApiFetch<ChatSession[]>(`/api/chat/sessions${q}`);
}



export async function deleteChatSession(sessionId: string): Promise<void> {
  await rateLimitedApiFetch<null>(`/api/chat/sessions/${sessionId}`, {
    method: "DELETE",
  });
}



export async function getChatMessages(
  sessionId: string
): Promise<ChatMessage[]> {
  return rateLimitedApiFetch<ChatMessage[]>(`/api/chat/sessions/${sessionId}/messages`);
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
    const contentType = res.headers.get("content-type") ?? "";
    try {
      if (contentType.includes("application/json")) {
        const body = (await res.json()) as { message?: string; detail?: string };
        message = body.message || body.detail || message;
      } else {
        const text = (await res.text()).trim();
        if (text) message = text;
      }
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }

  const streamContentType = res.headers.get("content-type") ?? "";
  if (streamContentType.includes("application/json")) {
    const body = (await res.json()) as { success?: boolean; message?: string };
    if (body.success === false) {
      throw new Error(body.message || "发送失败");
    }
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

// ── Agent 模式 ────────────────────────────────────────────

/** 格式校验单项检查结果 */
export type ValidationCheck = {
  rule: string;
  passed: boolean;
  message: string;
};

/** 格式校验事件载荷 */
export type ValidateEventPayload = {
  template_id: number;
  passed: boolean;
  failed_count: number;
  checks: ValidationCheck[];
  summary: string;
};

/** 返工事件载荷 */
export type ReworkEventPayload = {
  rework_count: number;
  failed_checks: ValidationCheck[];
};

export type StreamAgentOptions = {
  sessionId: string;
  content: string;
  docFile?: File | null;
  onThinking?: (round: number) => void;
  onStep?: (step: AgentStep) => void;
  onToken: (token: string) => void;
  onFile?: (file: AgentFile) => void;
  /** LangGraph validate 节点：按模板校验规则检查导出内容 */
  onValidate?: (payload: ValidateEventPayload) => void;
  /** LangGraph rework 节点：校验不通过返工通知 */
  onRework?: (payload: ReworkEventPayload) => void;
  /** 断点续跑成功 */
  onResumed?: (taskId: string) => void;
  onDone?: () => void;
  signal?: AbortSignal;
};

/**
 * Agent 模式 SSE 流式发送消息。
 * 事件类型：
 *   thinking（思考中）、step（工具调用）、token（文本）、file（文件）、
 *   validate（格式校验）、rework（返工）、resumed（断点续跑）、done（结束）
 */
export async function streamAgentMessage({
  sessionId,
  content,
  docFile,
  onThinking,
  onStep,
  onToken,
  onFile,
  onValidate,
  onRework,
  onResumed,
  onDone,
  signal,
}: StreamAgentOptions): Promise<void> {
  const form = new FormData();
  form.append("session_id", sessionId);
  form.append("content", content);

  if (docFile) {
    form.append("file", docFile, docFile.name);
  }

  const base = await ensureApiBaseUrl();
  const res = await fetch(`${base}/api/chat/agent/stream`, {
    method: "POST",
    body: form,
    signal,
  });

  if (!res.ok) {
    let message = `Agent 请求失败 (${res.status})`;
    const contentType = res.headers.get("content-type") ?? "";
    try {
      if (contentType.includes("application/json")) {
        const body = (await res.json()) as { message?: string; detail?: string };
        message = body.message || body.detail || message;
      } else {
        const text = (await res.text()).trim();
        if (text) message = text;
      }
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }

  if (!res.body) throw new Error("流式响应为空");

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
          type?: string;
          round?: number;
          step_id?: number;
          tool?: string;
          args?: Record<string, unknown>;
          result?: Record<string, unknown>;
          status?: string;
          token?: string;
          file?: AgentFile;
          done?: boolean;
          error?: string;
          // LangGraph validate / rework / resumed 事件
          template_id?: number;
          passed?: boolean;
          failed_count?: number;
          checks?: ValidationCheck[];
          summary?: string;
          rework_count?: number;
          failed_checks?: ValidationCheck[];
          task_id?: string;
        };

        if (data.error) throw new Error(data.error);

        if (data.type === "thinking") {
          onThinking?.(data.round ?? 1);
        }

        if (data.type === "step" && data.tool) {
          onStep?.({
            step_id: data.step_id ?? 0,
            tool: data.tool,
            args: data.args ?? {},
            result: data.result,
            status: (data.status as "running" | "done") ?? "running",
          });
        }

        if (data.type === "token" && data.token) {
          onToken(data.token);
        }

        if (data.type === "file" && data.file) {
          onFile?.(data.file);
        }

        if (data.type === "validate" && data.template_id != null) {
          onValidate?.({
            template_id: data.template_id,
            passed: data.passed ?? true,
            failed_count: data.failed_count ?? 0,
            checks: data.checks ?? [],
            summary: data.summary ?? "",
          });
        }

        if (data.type === "rework" && data.rework_count != null) {
          onRework?.({
            rework_count: data.rework_count,
            failed_checks: data.failed_checks ?? [],
          });
        }

        if (data.type === "resumed" && data.task_id) {
          onResumed?.(data.task_id);
        }

        if (data.type === "done" || data.done) {
          onDone?.();
        }
      } catch (e) {
        if (e instanceof SyntaxError) continue;
        throw e;
      }
    }
  }
}