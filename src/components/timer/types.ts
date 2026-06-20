export type StatsPeriod = "today" | "week" | "month" | "all";

export type TimerMode = "countdown" | "stopwatch";

export type TimerRunStatus = "idle" | "running" | "paused";

export interface TimerSubject {
  id: string;
  name: string;
  color: string;
  totalSeconds: number;
  createdAt: string;
}

export interface TimerSession {
  id: string;
  subjectId: string;
  subjectName: string;
  mode: "stopwatch" | "countdown";
  durationSeconds: number;
  startedAt: string;
  endedAt: string;
}

export interface SubjectStatItem {
  subjectId: string;
  name: string;
  color: string;
  durationSeconds: number;
  barPercent: number;
  percent: number;
}

export type StatsTab = "today" | "week" | "month" | "total";
