/** 番茄钟本地存储版本号 */
export const TOMATO_STORAGE_VERSION = 1 as const;

/** 统计周期 */
export type StatsPeriod = "today" | "week" | "month" | "all";

/** 计时模式：倒计时 / 正计时 */
export type TimerMode = "countdown" | "countup";

/** 计时运行状态 */
export type TimerRunStatus = "idle" | "running" | "paused";

/** 学习科目 */
export interface Subject {
  id: string;
  name: string;
  color: string;
  sortOrder: number;
  /** 累计学习时长（秒） */
  totalSeconds: number;
  createdAt: string;
}

/** 单次学习记录 */
export interface StudyRecord {
  id: string;
  subjectId: string;
  subjectName: string;
  durationSeconds: number;
  /** 本地日期 YYYY-MM-DD */
  dateKey: string;
  completedAt: string;
}

/** LocalStorage 完整数据结构 */
export interface TomatoStorage {
  version: typeof TOMATO_STORAGE_VERSION;
  /** 倒计时默认时长（分钟） */
  countdownMinutes: number;
  /** 每日目标（分钟），用于统计页进度环 */
  dailyGoalMinutes: number;
  subjects: Subject[];
  records: StudyRecord[];
}

/** 圆形进度环属性 */
export interface CircleProgressProps {
  percent: number;
  subtitle?: string;
  size?: number;
}

/** 条形图单项 */
export interface BarChartItem {
  subjectId: string;
  name: string;
  color: string;
  durationSeconds: number;
  barPercent: number;
  formattedDuration: string;
}

export interface BarChartProps {
  items: BarChartItem[];
}

/** 统计页汇总 */
export interface TomatoStatsSummary {
  period: StatsPeriod;
  totalSeconds: number;
  formattedTotal: string;
  goalPercent: number;
  dailyGoalSeconds: number;
  barItems: BarChartItem[];
}

/** 计时器对外状态 */
export interface TomatoTimerState {
  mode: TimerMode;
  status: TimerRunStatus;
  elapsedSeconds: number;
  remainingSeconds: number;
  totalSeconds: number;
  displayTime: string;
}
