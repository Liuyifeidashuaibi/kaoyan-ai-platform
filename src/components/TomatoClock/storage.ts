import {
  TOMATO_STORAGE_VERSION,
  type StudyRecord,
  type Subject,
  type TomatoStorage,
} from "@/components/TomatoClock/types";
import { toDateKey } from "@/components/TomatoClock/utils";

/** 番茄钟 LocalStorage 键名 */
export const STORAGE_KEY = "kaoyan-tomato-clock-v1";

const SUBJECT_COLORS = [
  "#3b82f6",
  "#6366f1",
  "#8b5cf6",
  "#0ea5e9",
  "#14b8a6",
  "#22c55e",
  "#f59e0b",
  "#ef4444",
] as const;

function createLocalId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function clampCountdownMinutes(value: number): number {
  return Math.min(60, Math.max(5, Math.round(value)));
}

export function createDefaultStorage(): TomatoStorage {
  return {
    version: TOMATO_STORAGE_VERSION,
    countdownMinutes: 25,
    dailyGoalMinutes: 240,
    subjects: [],
    records: [],
  };
}

function normalizeRecord(record: StudyRecord): StudyRecord {
  return {
    ...record,
    dateKey: record.dateKey || toDateKey(new Date(record.completedAt)),
  };
}

export function getTomatoStorage(): TomatoStorage {
  if (typeof window === "undefined") {
    return createDefaultStorage();
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return createDefaultStorage();
    }

    const parsed = JSON.parse(raw) as TomatoStorage & {
      workDurationMinutes?: number;
    };

    if (parsed.version !== TOMATO_STORAGE_VERSION) {
      return createDefaultStorage();
    }

    return {
      version: TOMATO_STORAGE_VERSION,
      countdownMinutes: clampCountdownMinutes(
        parsed.countdownMinutes ?? parsed.workDurationMinutes ?? 25
      ),
      dailyGoalMinutes: parsed.dailyGoalMinutes ?? 240,
      subjects: Array.isArray(parsed.subjects)
        ? [...parsed.subjects].sort((a, b) => a.sortOrder - b.sortOrder)
        : [],
      records: Array.isArray(parsed.records)
        ? parsed.records.map((item) => normalizeRecord(item as StudyRecord))
        : [],
    };
  } catch {
    return createDefaultStorage();
  }
}

export function setTomatoStorage(data: TomatoStorage): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    return true;
  } catch {
    return false;
  }
}

export function assignSubjectColor(index: number): string {
  return SUBJECT_COLORS[index % SUBJECT_COLORS.length];
}

export { createLocalId };

export function addSubjectToStorage(
  storage: TomatoStorage,
  name: string
): { storage: TomatoStorage; subject: Subject } | { error: string } {
  const trimmed = name.trim();
  if (trimmed.length < 1 || trimmed.length > 20) {
    return { error: "科目名称需为 1-20 个字符" };
  }

  if (
    storage.subjects.some(
      (item) => item.name.toLowerCase() === trimmed.toLowerCase()
    )
  ) {
    return { error: "该科目已存在" };
  }

  const subject: Subject = {
    id: createLocalId(),
    name: trimmed,
    color: assignSubjectColor(storage.subjects.length),
    sortOrder: storage.subjects.length,
    totalSeconds: 0,
    createdAt: new Date().toISOString(),
  };

  return {
    storage: { ...storage, subjects: [...storage.subjects, subject] },
    subject,
  };
}

export function removeSubjectFromStorage(
  storage: TomatoStorage,
  subjectId: string
): TomatoStorage {
  return {
    ...storage,
    subjects: storage.subjects.filter((item) => item.id !== subjectId),
    records: storage.records.filter((item) => item.subjectId !== subjectId),
  };
}

export function appendStudyRecord(
  storage: TomatoStorage,
  payload: {
    subjectId: string;
    subjectName: string;
    durationSeconds: number;
    completedAt?: string;
  }
): TomatoStorage {
  const completedAt = payload.completedAt ?? new Date().toISOString();
  const record: StudyRecord = {
    id: createLocalId(),
    subjectId: payload.subjectId,
    subjectName: payload.subjectName,
    durationSeconds: payload.durationSeconds,
    dateKey: toDateKey(new Date(completedAt)),
    completedAt,
  };

  const subjects = storage.subjects.map((subject) =>
    subject.id === payload.subjectId
      ? {
          ...subject,
          totalSeconds: subject.totalSeconds + payload.durationSeconds,
        }
      : subject
  );

  return {
    ...storage,
    subjects,
    records: [record, ...storage.records].slice(0, 1000),
  };
}
