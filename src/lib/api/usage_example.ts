import { smartFetch, smartUpload } from "./smart_client";
import { switchModel, getCurrentModel, autoSwitchModel } from "./model_switcher";

// 使用示例：获取聊天会话
export async function getChatSession(title = "新对话") {
  try {
    const session = await smartFetch<ChatSession>("/api/chat/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    return session;
  } catch (error) {
    console.error("获取聊天会话失败:", error);
    throw error;
  }
}

// 使用示例：发送消息
export async function sendMessage(sessionId: string, content: string) {
  try {
    const response = await smartFetch<MessageResponse>("/api/chat/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId, content }),
    });
    return response;
  } catch (error) {
    console.error("发送消息失败:", error);
    throw error;
  }
}

// 使用示例：上传文件
export async function uploadFile(path: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);
  
  try {
    const result = await smartUpload<UploadResponse>("/api/upload", formData);
    return result;
  } catch (error) {
    console.error("文件上传失败:", error);
    throw error;
  }
}

// 使用示例：手动切换模型
export function switchToGLM46() {
  switchModel("glm-4.6");
  console.log(`已切换到模型: ${getCurrentModel()}`);
}

// 使用示例：自动切换模型（在限流情况下）
export function handleRateLimit() {
  autoSwitchModel(3); // 传入连续限流次数
}

// 类型定义（假设）
interface ChatSession {
  id: string;
  title: string;
  createdAt: string;
}

interface MessageResponse {
  success: boolean;
  message: string;
}

interface UploadResponse {
  success: boolean;
  url: string;
}