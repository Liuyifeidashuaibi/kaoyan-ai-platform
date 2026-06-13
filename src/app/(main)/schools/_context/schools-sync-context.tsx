"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { prefetchSchoolsData } from "@/lib/api/schools";
import {
  fetchSchoolsDataFingerprint,
  fetchSchoolsSyncMeta,
  SCHOOLS_SYNC_POLL_MS,
  triggerSchoolsDataRefresh,
} from "@/lib/api/schools-sync";

type SchoolsSyncContextValue = {
  /** 递增版本号，子组件放入 useEffect 依赖以触发重载 */
  version: number;
  /** 最近一次同步时间文案 */
  lastSyncedLabel: string | null;
  syncing: boolean;
  /** 手动刷新（详情页/列表页刷新按钮） */
  refresh: () => Promise<void>;
};

const SchoolsSyncContext = createContext<SchoolsSyncContextValue | null>(null);

function formatSyncTime(iso: string | null): string | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", {
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return null;
  }
}

export function SchoolsSyncProvider({ children }: { children: ReactNode }) {
  const [version, setVersion] = useState(0);
  const [lastSyncedLabel, setLastSyncedLabel] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const revisionRef = useRef<number | null>(null);
  const fingerprintRef = useRef<string | null>(null);

  const applyMeta = useCallback((revision: number | null, updatedAt: string | null) => {
    if (updatedAt) setLastSyncedLabel(formatSyncTime(updatedAt));
    if (revision != null) revisionRef.current = revision;
  }, []);

  const bump = useCallback(() => {
    triggerSchoolsDataRefresh();
    setVersion((v) => v + 1);
  }, []);

  const checkRemote = useCallback(async () => {
    const meta = await fetchSchoolsSyncMeta();
    if (meta) {
      const prev = revisionRef.current;
      applyMeta(meta.revision, meta.updated_at);
      if (prev !== null && meta.revision > prev) {
        bump();
        return true;
      }
      if (prev === null) {
        revisionRef.current = meta.revision;
      }
      return false;
    }

    const fp = await fetchSchoolsDataFingerprint();
    const prevFp = fingerprintRef.current;
    fingerprintRef.current = fp;
    if (prevFp !== null && fp && fp !== prevFp) {
      bump();
      return true;
    }
    return false;
  }, [applyMeta, bump]);

  const refresh = useCallback(async () => {
    setSyncing(true);
    try {
      bump();
      await prefetchSchoolsData();
      const meta = await fetchSchoolsSyncMeta();
      if (meta) applyMeta(meta.revision, meta.updated_at);
    } finally {
      setSyncing(false);
    }
  }, [applyMeta, bump]);

  useEffect(() => {
    void (async () => {
      await checkRemote();
      await prefetchSchoolsData();
    })();

    const poll = () => {
      if (document.visibilityState !== "visible") return;
      void checkRemote();
    };

    const interval = setInterval(poll, SCHOOLS_SYNC_POLL_MS);
    document.addEventListener("visibilitychange", poll);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", poll);
    };
  }, [checkRemote]);

  return (
    <SchoolsSyncContext.Provider
      value={{ version, lastSyncedLabel, syncing, refresh }}
    >
      {children}
    </SchoolsSyncContext.Provider>
  );
}

export function useSchoolsSync(): SchoolsSyncContextValue {
  const ctx = useContext(SchoolsSyncContext);
  if (!ctx) {
    throw new Error("useSchoolsSync must be used within SchoolsSyncProvider");
  }
  return ctx;
}
