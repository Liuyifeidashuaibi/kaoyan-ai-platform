"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { syncLocalStudyDataToCloud } from "@/lib/study-timer/sync-service";
import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";

interface UseStudySyncOptions {
  onSynced?: () => void;
}

export function useStudySync(options: UseStudySyncOptions = {}) {
  const { onSynced } = options;
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const syncedRef = useRef(false);
  const onSyncedRef = useRef(onSynced);

  useEffect(() => {
    onSyncedRef.current = onSynced;
  }, [onSynced]);

  const runSync = useCallback(async (userId: string) => {
    if (syncedRef.current || syncing) {
      return;
    }

    setSyncing(true);
    setSyncMessage(null);

    const result = await syncLocalStudyDataToCloud(userId);

    setSyncing(false);

    if (result.error) {
      setSyncMessage(`本地数据同步失败：${result.error}`);
      return;
    }

    if (result.syncedSubjects > 0 || result.syncedSessions > 0) {
      setSyncMessage(
        `已同步 ${result.syncedSubjects} 个科目、${result.syncedSessions} 条计时记录至云端`
      );
      syncedRef.current = true;
      onSyncedRef.current?.();
      return;
    }

    syncedRef.current = true;
  }, [syncing]);

  useEffect(() => {
    if (!isSupabaseConfigured()) {
      return;
    }

    const supabase = createClient();

    supabase.auth.getUser().then(({ data: { user } }) => {
      if (user) {
        void runSync(user.id);
      }
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "SIGNED_IN" && session?.user) {
        syncedRef.current = false;
        void runSync(session.user.id);
      }

      if (event === "SIGNED_OUT") {
        syncedRef.current = false;
        setSyncMessage(null);
      }
    });

    return () => subscription.unsubscribe();
  }, [runSync]);

  return { syncing, syncMessage };
}
