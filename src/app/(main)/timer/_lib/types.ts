/** 统计周期 */
export type StatsPeriod = "today" | "week" | "month" | "all";

/** 计时模式：倒计时 / 正计时 */
export type TimerMode = "countdown" | "countup";

/** 计时运行状态 */
export type TimerRunStatus = "idle" | "running" | "paused";

/** 学习科目（来自 Supabase） */
export interface TimerSubject {
  id: string;
  name: string;
  color: string;
  totalSeconds: number;
  createdAt: string;
}

/** 计时会话记录（来自 Supabase） */
export interface TimerSession {
  id: string;
  subjectId: string;
  subjectName: string;
  mode: "stopwatch" | "countdown";
  durationSeconds: number;
  startedAt: string;
  endedAt: string;
}

/** 用户番茄钟偏好（本地存储） */
export interface TimerPreferences {
  countdownMinutes: number;
  dailyGoalMinutes: number;
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
export interface TimerStatsSummary {
  period: StatsPeriod;
  totalSeconds: number;
  formattedTotal: string;
  goalPercent: number;
  goalSeconds: number;
  barItems: BarChartItem[];
}

/** 计时器对外状态 */
export interface TimerState {
  mode: TimerMode;
  status: TimerRunStatus;
  elapsedSeconds: number;
  remainingSeconds: number;
  totalSeconds: number;
  displayTime: string;
}
