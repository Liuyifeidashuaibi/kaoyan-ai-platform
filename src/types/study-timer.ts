export type TimerMode = "stopwatch" | "countdown";

export type TimerStatus = "idle" | "running" | "paused" | "completed";

/** 科目实体（本地与云端统一结构） */
export interface StudySubject {
  id: string;
  name: string;
  color: string;
  totalSeconds: number;
  createdAt: string;
  updatedAt: string;
}

/** 单次计时记录 */
export interface StudyTimerSession {
  id: string;
  subjectId: string;
  mode: TimerMode;
  durationSeconds: number;
  startedAt: string;
  endedAt: string;
  createdAt: string;
}

/** 创建科目入参 */
export interface CreateStudySubjectInput {
  name: string;
}

/** 写入计时记录入参 */
export interface RecordStudySessionInput {
  subjectId: string;
  mode: TimerMode;
  durationSeconds: number;
  startedAt: string;
  endedAt: string;
}

/** localStorage 持久化结构 */
export interface LocalStudyTimerStore {
  version: 1;
  subjects: StudySubject[];
  sessions: StudyTimerSession[];
}

/** 仓库层统一返回结构 */
export interface StudyTimerRepositoryResult<T> {
  data: T | null;
  error: string | null;
}

/** 计时引擎对外状态 */
export interface TimerEngineState {
  status: TimerStatus;
  mode: TimerMode;
  /** 当前会话已计秒数（不含历史暂停前已入库部分） */
  sessionElapsedSeconds: number;
  /** 倒计时目标秒数 */
  countdownTargetSeconds: number;
  /** 倒计时剩余秒数 */
  countdownRemainingSeconds: number;
}

/** 计时引擎配置 */
export interface UseTimerEngineOptions {
  mode: TimerMode;
  countdownTargetSeconds: number;
  onSessionComplete: (payload: {
    durationSeconds: number;
    startedAt: string;
    endedAt: string;
  }) => Promise<void>;
  onError: (message: string) => void;
}

/** 科目统计项 */
export interface SubjectStatItem {
  subject: StudySubject;
  formattedDuration: string;
  percentage: number;
}

/** 同步结果 */
export interface StudySyncResult {
  syncedSubjects: number;
  syncedSessions: number;
  error: string | null;
}
