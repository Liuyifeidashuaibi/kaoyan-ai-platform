// 智能请求客户端配置
export interface ModelConfig {
  name: string;
  maxConcurrent: number;
  requestInterval: number;
  jitterRange: number;
  maxRetries: number;
  backoffBase: number;
  rateLimitErrors: number[];
  fallbackModel: string;
  maxConsecutiveRateLimits: number;
}

// 模型配置映射
export const MODEL_CONFIGS: Record<string, ModelConfig> = {
  // glm-5.1 配置
  'glm-5.1': {
    name: 'glm-5.1',
    maxConcurrent: 10,
    requestInterval: 500,
    jitterRange: 300,
    maxRetries: 5,
    backoffBase: 1000,
    rateLimitErrors: [429, 1302],
    fallbackModel: 'glm-4.6',
    maxConsecutiveRateLimits: 3
  },
  
  // glm-4.6 配置
  'glm-4.6': {
    name: 'glm-4.6',
    maxConcurrent: 8,
    requestInterval: 600,
    jitterRange: 400,
    maxRetries: 3,
    backoffBase: 800,
    rateLimitErrors: [429, 1302],
    fallbackModel: 'glm-3.5',
    maxConsecutiveRateLimits: 3
  },
  
  // glm-3.5 配置
  'glm-3.5': {
    name: 'glm-3.5',
    maxConcurrent: 5,
    requestInterval: 800,
    jitterRange: 500,
    maxRetries: 2,
    backoffBase: 600,
    rateLimitErrors: [429, 1302],
    fallbackModel: 'glm-2.9',
    maxConsecutiveRateLimits: 3
  }
};

// 获取模型配置
export function getModelConfig(modelName: string): ModelConfig {
  const config = MODEL_CONFIGS[modelName.toLowerCase()];
  if (!config) {
    throw new Error(`未找到模型配置: ${modelName}`);
  }
  return config;
}

// 切换模型配置（延迟导入避免循环依赖）
export function switchModelConfig(modelName: string): void {
  import("./smart_client").then(({ getSmartApiClient }) => {
    const client = getSmartApiClient();
    const newConfig = getModelConfig(modelName);
    client.updateConfig(newConfig);
    console.log(`[Smart Client] 已切换到模型: ${modelName}`);
  });
}