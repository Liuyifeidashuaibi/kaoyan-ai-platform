import {
  createCloudSubject,
  getCloudSubjectById,
  listCloudSubjects,
  recordCloudSession,
} from "@/lib/study-timer/cloud-repository";
import {
  createLocalSubject,
  getLocalSubjectById,
  listLocalSubjects,
  recordLocalSession,
} from "@/lib/study-timer/local-storage";
import { createClient } from "@/lib/supabase/client";
import type {
  CreateStudySubjectInput,
  RecordStudySessionInput,
  StudySubject,
  StudyTimerRepositoryResult,
} from "@/types/study-timer";

interface AuthContext {
  userId: string | null;
}

async function resolveAuthContext(): Promise<AuthContext> {
  try {
    const supabase = createClient();
    const {
      data: { user },
      error,
    } = await supabase.auth.getUser();

    if (error || !user) {
      return { userId: null };
    }

    return { userId: user.id };
  } catch {
    return { userId: null };
  }
}

export async function fetchStudySubjects(): Promise<
  StudyTimerRepositoryResult<StudySubject[]>
> {
  const { userId } = await resolveAuthContext();

  if (!userId) {
    return listLocalSubjects();
  }

  try {
    const supabase = createClient();
    return await listCloudSubjects(supabase, userId);
  } catch (error) {
    const fallback = listLocalSubjects();
    return {
      data: fallback.data,
      error:
        error instanceof Error
          ? `云端加载失败，已降级为本地数据：${error.message}`
          : "云端加载失败，已降级为本地数据",
    };
  }
}

export async function fetchStudySubjectById(
  subjectId: string
): Promise<StudyTimerRepositoryResult<StudySubject>> {
  const { userId } = await resolveAuthContext();

  if (!userId) {
    return getLocalSubjectById(subjectId);
  }

  try {
    const supabase = createClient();
    return await getCloudSubjectById(supabase, userId, subjectId);
  } catch (error) {
    return {
      data: null,
      error: error instanceof Error ? error.message : "加载科目失败",
    };
  }
}

export async function createStudySubject(
  input: CreateStudySubjectInput
): Promise<StudyTimerRepositoryResult<StudySubject>> {
  const { userId } = await resolveAuthContext();

  if (!userId) {
    return createLocalSubject(input);
  }

  try {
    const supabase = createClient();
    const existing = await listCloudSubjects(supabase, userId);
    const colorIndex = existing.data?.length ?? 0;
    return await createCloudSubject(supabase, userId, input, colorIndex);
  } catch (error) {
    return {
      data: null,
      error: error instanceof Error ? error.message : "创建科目失败",
    };
  }
}

export async function persistStudySession(
  input: RecordStudySessionInput
): Promise<StudyTimerRepositoryResult<StudySubject>> {
  const { userId } = await resolveAuthContext();

  if (!userId) {
    const result = recordLocalSession(input);
    if (result.error || !result.data) {
      return { data: null, error: result.error ?? "保存计时记录失败" };
    }
    return getLocalSubjectById(input.subjectId);
  }

  try {
    const supabase = createClient();
    const recordResult = await recordCloudSession(supabase, userId, input);

    if (recordResult.error) {
      const localFallback = recordLocalSession(input);
      const localSubject = getLocalSubjectById(input.subjectId);
      return {
        data: localSubject.data,
        error: `云端保存失败，已写入本地：${recordResult.error}`,
      };
    }

    const subjectResult = await getCloudSubjectById(
      supabase,
      userId,
      input.subjectId
    );
    return subjectResult;
  } catch (error) {
    recordLocalSession(input);
    const localSubject = getLocalSubjectById(input.subjectId);
    return {
      data: localSubject.data,
      error:
        error instanceof Error
          ? `网络异常，已降级本地存储：${error.message}`
          : "网络异常，已降级本地存储",
    };
  }
}

export async function getCurrentUserId(): Promise<string | null> {
  const { userId } = await resolveAuthContext();
  return userId;
}
