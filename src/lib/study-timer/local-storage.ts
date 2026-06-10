import {
  LOCAL_STUDY_TIMER_STORAGE_KEY,
  SUBJECT_NAME_MAX_LENGTH,
} from "@/lib/study-timer/constants";
import {
  assignSubjectColor,
  createClientId,
  isValidSubjectName,
  normalizeSubjectName,
} from "@/lib/study-timer/utils";
import type {
  CreateStudySubjectInput,
  LocalStudyTimerStore,
  RecordStudySessionInput,
  StudySubject,
  StudyTimerRepositoryResult,
  StudyTimerSession,
} from "@/types/study-timer";

function createEmptyStore(): LocalStudyTimerStore {
  return { version: 1, subjects: [], sessions: [] };
}

function readStore(): LocalStudyTimerStore {
  if (typeof window === "undefined") {
    return createEmptyStore();
  }

  try {
    const raw = window.localStorage.getItem(LOCAL_STUDY_TIMER_STORAGE_KEY);
    if (!raw) {
      return createEmptyStore();
    }

    const parsed = JSON.parse(raw) as LocalStudyTimerStore;
    if (parsed.version !== 1 || !Array.isArray(parsed.subjects)) {
      return createEmptyStore();
    }

    return {
      version: 1,
      subjects: parsed.subjects,
      sessions: Array.isArray(parsed.sessions) ? parsed.sessions : [],
    };
  } catch {
    return createEmptyStore();
  }
}

function writeStore(store: LocalStudyTimerStore): StudyTimerRepositoryResult<true> {
  try {
    window.localStorage.setItem(
      LOCAL_STUDY_TIMER_STORAGE_KEY,
      JSON.stringify(store)
    );
    return { data: true, error: null };
  } catch (error) {
    return {
      data: null,
      error:
        error instanceof Error ? error.message : "本地存储写入失败，请检查浏览器权限",
    };
  }
}

export function loadLocalStudyStore(): LocalStudyTimerStore {
  return readStore();
}

export function clearLocalStudyStore(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(LOCAL_STUDY_TIMER_STORAGE_KEY);
}

export function listLocalSubjects(): StudyTimerRepositoryResult<StudySubject[]> {
  const store = readStore();
  return {
    data: [...store.subjects].sort(
      (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    ),
    error: null,
  };
}

export function createLocalSubject(
  input: CreateStudySubjectInput
): StudyTimerRepositoryResult<StudySubject> {
  const name = normalizeSubjectName(input.name);

  if (!isValidSubjectName(name, SUBJECT_NAME_MAX_LENGTH)) {
    return { data: null, error: "科目名称不能为空且不超过 32 个字符" };
  }

  const store = readStore();
  const duplicated = store.subjects.some(
    (subject) => subject.name.toLowerCase() === name.toLowerCase()
  );

  if (duplicated) {
    return { data: null, error: "该科目名称已存在" };
  }

  const now = new Date().toISOString();
  const subject: StudySubject = {
    id: createClientId(),
    name,
    color: assignSubjectColor(store.subjects.length),
    totalSeconds: 0,
    createdAt: now,
    updatedAt: now,
  };

  store.subjects.unshift(subject);
  const writeResult = writeStore(store);

  if (writeResult.error) {
    return { data: null, error: writeResult.error };
  }

  return { data: subject, error: null };
}

export function getLocalSubjectById(
  subjectId: string
): StudyTimerRepositoryResult<StudySubject> {
  const store = readStore();
  const subject = store.subjects.find((item) => item.id === subjectId) ?? null;
  return subject
    ? { data: subject, error: null }
    : { data: null, error: "科目不存在" };
}

export function incrementLocalSubjectTotal(
  subjectId: string,
  deltaSeconds: number
): StudyTimerRepositoryResult<StudySubject> {
  if (deltaSeconds <= 0) {
    return { data: null, error: "无效的计时时长" };
  }

  const store = readStore();
  const index = store.subjects.findIndex((item) => item.id === subjectId);

  if (index === -1) {
    return { data: null, error: "科目不存在" };
  }

  const current = store.subjects[index];
  const updated: StudySubject = {
    ...current,
    totalSeconds: current.totalSeconds + deltaSeconds,
    updatedAt: new Date().toISOString(),
  };

  store.subjects[index] = updated;
  const writeResult = writeStore(store);

  if (writeResult.error) {
    return { data: null, error: writeResult.error };
  }

  return { data: updated, error: null };
}

export function recordLocalSession(
  input: RecordStudySessionInput
): StudyTimerRepositoryResult<StudyTimerSession> {
  const incrementResult = incrementLocalSubjectTotal(
    input.subjectId,
    input.durationSeconds
  );

  if (incrementResult.error || !incrementResult.data) {
    return { data: null, error: incrementResult.error ?? "写入计时记录失败" };
  }

  const store = readStore();
  const session: StudyTimerSession = {
    id: createClientId(),
    subjectId: input.subjectId,
    mode: input.mode,
    durationSeconds: input.durationSeconds,
    startedAt: input.startedAt,
    endedAt: input.endedAt,
    createdAt: new Date().toISOString(),
  };

  store.sessions.unshift(session);
  const writeResult = writeStore(store);

  if (writeResult.error) {
    return { data: null, error: writeResult.error };
  }

  return { data: session, error: null };
}

/** 导入本地数据（同步后合并用） */
export function importLocalStore(store: LocalStudyTimerStore): StudyTimerRepositoryResult<true> {
  return writeStore(store);
}
