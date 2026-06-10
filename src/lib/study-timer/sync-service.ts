import {
  clearLocalStudyStore,
  loadLocalStudyStore,
} from "@/lib/study-timer/local-storage";
import {
  insertCloudSessionIfNotExists,
  upsertCloudSubjectByName,
} from "@/lib/study-timer/cloud-repository";
import { createClient } from "@/lib/supabase/client";
import type { StudySyncResult } from "@/types/study-timer";

/**
 * 将 localStorage 中的科目与计时记录同步至 Supabase。
 * 按科目名称合并累计时长，按 startedAt+duration 去重 sessions。
 */
export async function syncLocalStudyDataToCloud(
  userId: string
): Promise<StudySyncResult> {
  const localStore = loadLocalStudyStore();

  if (localStore.subjects.length === 0) {
    return { syncedSubjects: 0, syncedSessions: 0, error: null };
  }

  const supabase = createClient();
  let syncedSubjects = 0;
  let syncedSessions = 0;
  const subjectIdMap = new Map<string, string>();

  try {
    for (const subject of localStore.subjects) {
      const upsertResult = await upsertCloudSubjectByName(
        supabase,
        userId,
        subject
      );

      if (upsertResult.error || !upsertResult.data) {
        return {
          syncedSubjects,
          syncedSessions,
          error: upsertResult.error ?? "科目同步失败",
        };
      }

      subjectIdMap.set(subject.id, upsertResult.data.id);
      syncedSubjects += 1;
    }

    for (const session of localStore.sessions) {
      const cloudSubjectId = subjectIdMap.get(session.subjectId);
      if (!cloudSubjectId) {
        continue;
      }

      const insertResult = await insertCloudSessionIfNotExists(
        supabase,
        userId,
        cloudSubjectId,
        { ...session, subjectId: cloudSubjectId }
      );

      if (insertResult.error) {
        return {
          syncedSubjects,
          syncedSessions,
          error: insertResult.error,
        };
      }

      syncedSessions += 1;
    }

    clearLocalStudyStore();
    return { syncedSubjects, syncedSessions, error: null };
  } catch (error) {
    return {
      syncedSubjects,
      syncedSessions,
      error: error instanceof Error ? error.message : "同步过程中发生未知错误",
    };
  }
}
