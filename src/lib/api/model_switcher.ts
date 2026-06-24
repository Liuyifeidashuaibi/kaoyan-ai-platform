import { getSmartApiClient } from "./smart_client";
import { getModelConfig, switchModelConfig } from "./config";

// 模型切换器类
export class ModelSwitcher {
  private client: any;
  private currentModel: string;

  constructor() {
    this.client = getSmartApiClient();
    this.currentModel = 'glm-5.1';
  }

  // 切换模型
  switchModel(modelName: string): void {
    try {
      const newConfig = getModelConfig(modelName);
      this.client.updateConfig(newConfig);
      this.currentModel = modelName;
      console.log(`[Model Switcher] 已切换到模型: ${modelName}`);
    } catch (error) {
      console.error(`[Model Switcher] 切换模型失败: ${error}`);
    }
  }

  // 获取当前模型
  getCurrentModel(): string {
    return this.currentModel;
  }

  // 自动切换（基于限流情况）
  autoSwitch(consecutiveRateLimits: number): void {
    if (consecutiveRateLimits >= 3) {
      // 连续3次限流，切换到备用模型
      const currentConfig = getModelConfig(this.currentModel);
      const fallbackModel = currentConfig.fallbackModel;
      
      if (fallbackModel && fallbackModel !== this.currentModel) {
        this.switchModel(fallbackModel);
      }
    }
  }

  // 重置到默认模型
  resetToDefault(): void {
    this.switchModel('glm-5.1');
  }
}

// 单例实例
let modelSwitcherInstance: ModelSwitcher | null = null;

export function getModelSwitcher(): ModelSwitcher {
  if (!modelSwitcherInstance) {
    modelSwitcherInstance = new ModelSwitcher();
  }
  return modelSwitcherInstance;
}

// 导出便捷方法
export function switchModel(modelName: string): void {
  const switcher = getModelSwitcher();
  switcher.switchModel(modelName);
}

export function getCurrentModel(): string {
  const switcher = getModelSwitcher();
  return switcher.getCurrentModel();
}

export function autoSwitchModel(consecutiveRateLimits: number): void {
  const switcher = getModelSwitcher();
  switcher.autoSwitch(consecutiveRateLimits);
}