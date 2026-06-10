/** localStorage 键名 */
export const LOCAL_STUDY_TIMER_STORAGE_KEY = "kaoyan-study-timer-v1";

/** 科目名称最大长度 */
export const SUBJECT_NAME_MAX_LENGTH = 32;

/** 倒计时时长预设（分钟） */
export const COUNTDOWN_PRESETS_MINUTES = [25, 40, 45, 60, 90] as const;

/** 倒计时时长范围（分钟） */
export const COUNTDOWN_MIN_MINUTES = 1;
export const COUNTDOWN_MAX_MINUTES = 180;

/** 科目标识色板（按创建顺序循环分配） */
export const SUBJECT_COLOR_PALETTE = [
  "#6366F1",
  "#EC4899",
  "#F97316",
  "#22C55E",
  "#06B6D4",
  "#A855F7",
  "#EAB308",
  "#EF4444",
  "#14B8A6",
  "#8B5CF6",
] as const;

/** 计时 UI 刷新间隔（毫秒）— 仅用于展示，实际计时时钟基于 performance.now */
export const TIMER_DISPLAY_TICK_MS = 250;

/** 科目名称输入防抖（毫秒） */
export const SUBJECT_NAME_DEBOUNCE_MS = 300;

/** 通知权限请求延迟（毫秒） */
export const NOTIFICATION_REQUEST_DELAY_MS = 500;
