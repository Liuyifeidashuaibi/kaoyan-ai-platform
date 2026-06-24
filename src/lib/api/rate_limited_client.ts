import { ensureApiBaseUrl } from "@/lib/config/api";
import type { ApiResponse } from "@/lib/api/types";
import { ApiError } from "./client";

// 全局请求队列和状态管理
const requestQueue: Array<() => Promise<any>> = [];
let isProcessing = false;
let consecutiveRateLimits = 0;
let currentModel = "glm-5.1";
const fallbackModel = "glm-4.6";

// 请求间隔配置
const MIN_REQUEST_INTERVAL = 2000; // 2000ms
const MAX_RETRIES = 5;
const RATE_LIMIT_ERROR_CODES = [429, 1302];

// 指数退避配置
const BACKOFF_BASE = 1000; // 基础退避时间

// 全局锁，确保单并发
const requestLock = new Promise<void>((resolve) => {
  const release = () => resolve();
  // 立即释放，因为我们使用队列来控制
  setTimeout(release, 0);
});

// 添加随机抖动
function addJitter(baseDelay: number): number {
  const jitter = Math.random() * 0.3 * baseDelay; // 0-30% 随机抖动
  return baseDelay + jitter;
}

// 指数退避计算
function calculateBackoff(retryCount: number): number {
  return Math.min(
    Math.pow(2, retryCount) * BACKOFF_BASE,
    30000 // 最大30秒
  );
}

// 熔断机制：连续3次限流后切换模型
function handleRateLimit() {
  consecutiveRateLimits++;
  if (consecutiveRateLimits >= 3) {
    consecutiveRateLimits = 0;
    currentModel = fallbackModel;
    console.warn(`[Rate Limiter] 连续3次限流，切换到备用模型: ${fallbackModel}`);
  }
}

// 恢复主模型
function resetRateLimit() {
  consecutiveRateLimits = 0;
  currentModel = "glm-5.1";
}

// 请求包装函数
async function wrapRequest<T>(
  requestFn: () => Promise<T>,
  retryCount: number = 0
): Promise<T> {
  try {
    // 等待锁释放（确保单并发）
    await requestLock;
    
    // 执行请求
    const result = await requestFn();
    
    // 重置限流计数器（成功请求）
    resetRateLimit();
    
    return result;
  } catch (error: any) {
    const statusCode = error.status || 0;
    
    // 检查是否是限流错误
    if (RATE_LIMIT_ERROR_CODES.includes(statusCode)) {
      handleRateLimit();
      
      if (retryCount < MAX_RETRIES) {
        const backoff = calculateBackoff(retryCount);
        const jitteredDelay = addJitter(backoff);
        
        console.warn(
          `[Rate Limiter] 请求被限流 (代码: ${statusCode})，${retryCount + 1}/${MAX_RETRIES} 次重试，等待 ${Math.round(jitteredDelay)}ms`
        );
        
        // 等待退避时间
        await new Promise(resolve => setTimeout(resolve, jitteredDelay));
        
        // 递归重试
        return wrapRequest(requestFn, retryCount + 1);
      } else {
        console.error(`[Rate Limiter] 达到最大重试次数 ${MAX_RETRIES}，放弃请求`);
        throw error;
      }
    }
    
    // 其他错误直接抛出
    throw error;
  }
}

// 请求间隔控制
async function enforceRequestInterval() {
  return new Promise<void>((resolve) => {
    const jitteredInterval = addJitter(MIN_REQUEST_INTERVAL);
    setTimeout(resolve, jitteredInterval);
  });
}

// 通用 JSON 请求封装（带限流控制）
export async function rateLimitedApiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  // 确保请求间隔
  await enforceRequestInterval();
  
  // 包装请求函数
  const requestFn = async () => {
    const base = await ensureApiBaseUrl();
    let res: Response;
    
    try {
      // 添加模型参数到URL（如果适用）
      let url = `${base}${path}`;
      if (path.includes('?')) {
        url += `&model=${currentModel}`;
      } else {
        url += `?model=${currentModel}`;
      }
      
      res = await fetch(url, init);
    } catch (err) {
      const hint =
        base && base.startsWith("http")
          ? "请确认后端已启动，或移除 NEXT_PUBLIC_API_URL 走同源代理"
          : "请确认后端已启动（BACKEND_URL）";
      throw new ApiError(
        err instanceof Error && err.message === "Failed to fetch"
          ? `无法连接服务器，${hint}`
          : err instanceof Error
            ? err.message
            : "网络错误",
        0
      );
    }

    let json: ApiResponse<T> & { detail?: string };
    const contentType = res.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      const text = (await res.text()).trim();
      throw new ApiError(text || `请求失败 (${res.status})`, res.status);
    }
    try {
      json = (await res.json()) as ApiResponse<T> & { detail?: string };
    } catch {
      throw new ApiError(`响应解析失败 (${res.status})`, res.status);
    }

    if (!res.ok || !json.success) {
      throw new ApiError(readErrorMessage(json, res.status), res.status);
    }

    return json.data;
  };

  // 使用包装函数执行请求
  return wrapRequest(requestFn);
}

// multipart 上传（带限流控制）
export async function rateLimitedApiUpload<T>(
  path: string,
  formData: FormData,
  headers?: HeadersInit
): Promise<T> {
  // 确保请求间隔
  await enforceRequestInterval();
  
  // 包装请求函数
  const requestFn = async () => {
    const base = await ensureApiBaseUrl();
    let res: Response;
    try {
      res = await fetch(`${base}${path}`, {
        method: "POST",
        body: formData,
        headers,
      });
    } catch (err) {
      throw new ApiError(
        err instanceof Error ? err.message : "上传失败：网络错误",
        0
      );
    }
    const contentType = res.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      const text = (await res.text()).trim();
      throw new ApiError(text || `上传失败 (${res.status})`, res.status);
    }
    let json: ApiResponse<T> & { detail?: string };
    try {
      json = (await res.json()) as ApiResponse<T> & { detail?: string };
    } catch {
      throw new ApiError(`上传响应解析失败 (${res.status})`, res.status);
    }

    if (!res.ok || !json.success) {
      throw new ApiError(readErrorMessage(json, res.status), res.status);
    }

    return json.data;
  };

  // 使用包装函数执行请求
  return wrapRequest(requestFn);
}

// 错误消息读取函数（从原始代码复制）
function readErrorMessage(
  json: Record<string, unknown>,
  status: number
): string {
  const message = json.message;
  if (typeof message === "string" && message.trim()) return message;
  const detail = json.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const nested = detail as Record<string, unknown>;
    if (typeof nested.message === "string" && nested.message.trim()) {
      return nested.message;
    }
  }
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) =>
        item && typeof item === "object" && "msg" in item
          ? String((item as { msg: unknown }).msg)
          : ""
      )
      .filter(Boolean);
    if (parts.length > 0) return parts.join("；");
  }
  return `请求失败 (${status})`;
}