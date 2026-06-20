"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchTaskStatus,
  type AsyncTaskRecord,
} from "@/lib/api/tasks";

/**
 * 轮询异步任务进度 — 参考 admin agent-control-center 模式。
 * 仅在 pending/running 时轮询，完成或失败后自动停止。
 */
export function useTaskPolling(
  taskId: string | null,
  options?: { intervalMs?: number; enabled?: boolean }
) {
  const intervalMs = options?.intervalMs ?? 2000;
  const enabled = options?.enabled ?? true;
  const [task, setTask] = useState<AsyncTaskRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setIsPolling(false);
  }, []);

  const refresh = useCallback(async () => {
    if (!taskId) return;
    try {
      const record = await fetchTaskStatus(taskId);
      setTask(record);
      setError(null);
      if (record.status === "done" || record.status === "failed") {
        stop();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "轮询失败");
    }
  }, [taskId, stop]);

  useEffect(() => {
    if (!taskId || !enabled) {
      stop();
      return;
    }
    void refresh();
    setIsPolling(true);
    timerRef.current = setInterval(() => void refresh(), intervalMs);
    return stop;
  }, [taskId, enabled, intervalMs, refresh, stop]);

  return { task, error, isPolling, refresh, stop };
}
