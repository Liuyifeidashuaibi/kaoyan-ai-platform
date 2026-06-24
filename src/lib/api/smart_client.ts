import { ensureApiBaseUrl } from "@/lib/config/api";
import type { ApiResponse } from "@/lib/api/types";
import { ApiError } from "./client";
import { getModelConfig } from "./config";

// 智能客户端类
export class SmartApiClient {
  private config: any;
  private consecutiveRateLimits = 0;
  private activeRequests = 0;

  constructor(modelName: string = 'glm-5.1') {
    this.config = getModelConfig(modelName);
  }

  // 更新配置
  updateConfig(newConfig: any) {
    this.config = newConfig;
    this.consecutiveRateLimits = 0;
  }

  // 添加随机抖动
  private addJitter(baseDelay: number): number {
    const jitter = Math.random() * this.config.jitterRange;
    return baseDelay + jitter;
  }

  // 指数退避计算
  private calculateBackoff(retryCount: number): number {
    return Math.min(
      Math.pow(2, retryCount) * this.config.backoffBase,
      30000 // 最大30秒
    );
  }

  // 检查是否是限流错误
  private isRateLimitError(error: any): boolean {
    if (error.response) {
      return this.config.rateLimitErrors.includes(error.response.status);
    }
    return false;
  }

  // 处理限流错误
  private handleRateLimit() {
    this.consecutiveRateLimits++;
    
    if (this.consecutiveRateLimits >= this.config.maxConsecutiveRateLimits) {
      this.consecutiveRateLimits = 0;
      console.warn(`[Smart Client] 连续3次限流，切换到备用模型: ${this.config.fallbackModel}`);
      // 这里可以添加模型切换逻辑
    }
  }

  // 重置限流计数器
  private resetRateLimit() {
    this.consecutiveRateLimits = 0;
  }

  // 请求包装函数
  private async wrapRequest<T>(requestFn: () => Promise<T>, retryCount: number = 0): Promise<T> {
    try {
      // 等待请求间隔
      await new Promise(resolve => setTimeout(resolve, this.addJitter(this.config.requestInterval)));
      
      // 等待并发控制
      while (this.activeRequests >= this.config.maxConcurrent) {
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      
      // 增加活跃请求数
      this.activeRequests++;
      
      // 执行请求
      const result = await requestFn();
      
      // 重置限流计数器
      this.resetRateLimit();
      
      // 减少活跃请求数
      this.activeRequests--;
      
      return result;
    } catch (error: any) {
      // 减少活跃请求数
      this.activeRequests--;
      
      // 检查是否是限流错误
      if (this.isRateLimitError(error)) {
        this.handleRateLimit();
        
        if (retryCount < this.config.maxRetries) {
          const backoff = this.calculateBackoff(retryCount);
          const jitteredDelay = this.addJitter(backoff);
          
          console.warn(
            `[Smart Client] 请求被限流，${retryCount + 1}/${this.config.maxRetries} 次重试，等待 ${Math.round(jitteredDelay)}ms`
          );
          
          // 等待退避时间
          await new Promise(resolve => setTimeout(resolve, jitteredDelay));
          
          // 递归重试
          return this.wrapRequest(requestFn, retryCount + 1);
        } else {
          console.error(`[Smart Client] 达到最大重试次数 ${this.config.maxRetries}，放弃请求`);
          throw error;
        }
      }
      
      // 其他错误直接抛出
      throw error;
    }
  }

  // 通用 JSON 请求
  async fetch<T>(path: string, init?: RequestInit): Promise<T> {
    const requestFn = async () => {
      const base = await ensureApiBaseUrl();
      let res: Response;
      
      try {
        res = await fetch(`${base}${path}`, init);
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

    return this.wrapRequest(requestFn);
  }

  // multipart 上传
  async upload<T>(path: string, formData: FormData, headers?: HeadersInit): Promise<T> {
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

    return this.wrapRequest(requestFn);
  }
}

// 错误消息读取函数
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

// 创建单例实例
let smartClientInstance: SmartApiClient | null = null;

export function getSmartApiClient(): SmartApiClient {
  if (!smartClientInstance) {
    smartClientInstance = new SmartApiClient();
  }
  return smartClientInstance;
}

// 导出便捷方法
export async function smartFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const client = getSmartApiClient();
  return client.fetch<T>(path, init);
}

export async function smartUpload<T>(path: string, formData: FormData, headers?: HeadersInit): Promise<T> {
  const client = getSmartApiClient();
  return client.upload<T>(path, formData, headers);
}