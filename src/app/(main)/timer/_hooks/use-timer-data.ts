"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getTimerPreferences,
  setTimerPreferences,
} from "@/app/(main)/timer/_lib/preferences";
import {
  createSubject,
  deleteSubject,
  fetchTimerData,
  getCurrentUserId,
  saveTimerSession,
} from "@/app/(main)/timer/_lib/repository";
import type {
  TimerPreferences,
  TimerSession,
  TimerSubject,
} from "@/app/(main)/timer/_lib/types";
import { clampCountdownMinutes } from "@/app/(main)/timer/_lib/utils";
import { isSupabaseConfigured } from "@/lib/supabase/client";

type LoadStatus = "loading" | "ready" | "error" | "unauthenticated" | "unconfigured";

export function useTimerData() {
  const [status, setStatus] = useState<LoadStatus>("loading");
  const [userId, setUserId] = useState<string | null>(null);
  const [subjects, setSubjects] = useState<TimerSubject[]>([]);
  const [sessions, setSessions] = useState<TimerSession[]>([]);
  const [preferences, setPreferences] = useState<TimerPreferences>(
    getTimerPreferences
  );
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const loadData = useCallback(async () => {
    if (!isSupabaseConfigured()) {
      setStatus("unconfigured");
      setError("Supabase 未配置，无法保存番茄钟数据");
      return;
    }

    setStatus("loading");
    setError(null);

    try {
      const uid = await getCurrentUserId();
      if (!uid) {
        setStatus("unauthenticated");
        setUserId(null);
        setSubjects([]);
        setSessions([]);
        return;
      }

      setUserId(uid);
      const data = await fetchTimerData(uid);
      setSubjects(data.subjects);
      setSessions(data.sessions);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "番茄钟数据加载失败");
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const addSubject = useCallback(
    async (name: string): Promise<string | null> => {
      if (!userId) {
        return null;
      }

      setSaving(true);
      setError(null);

      try {
        const subject = await createSubject(userId, name, subjects.length);
        setSubjects((prev) => [...prev, subject]);
        return subject.id;
      } catch (err) {
        setError(err instanceof Error ? err.message : "添加科目失败");
        return null;
      } finally {
        setSaving(false);
      }
    },
    [subjects.length, userId]
  );

  const removeSubject = useCallback(
    async (subjectId: string): Promise<boolean> => {
      setSaving(true);
      setError(null);

      try {
        await deleteSubject(subjectId);
        setSubjects((prev) => prev.filter((item) => item.id !== subjectId));
        setSessions((prev) =>
          prev.filter((item) => item.subjectId !== subjectId)
        );
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : "删除科目失败");
        return false;
      } finally {
        setSaving(false);
      }
    },
    []
  );

  const recordSession = useCallback(
    async (payload: {
      subjectId: string;
      subjectName: string;
      mode: "stopwatch" | "countdown";
      durationSeconds: number;
      startedAt: string;
      endedAt?: string;
    }): Promise<boolean> => {
      if (!userId || payload.durationSeconds <= 0) {
        return false;
      }

      setSaving(true);
      setError(null);

      const endedAt = payload.endedAt ?? new Date().toISOString();

      try {
        const session = await saveTimerSession({
          userId,
          subjectId: payload.subjectId,
          mode: payload.mode,
          durationSeconds: payload.durationSeconds,
          startedAt: payload.startedAt,
          endedAt,
        });

        const enriched: TimerSession = {
          ...session,
          subjectName: payload.subjectName,
        };

        setSessions((prev) => [enriched, ...prev]);
        setSubjects((prev) =>
          prev.map((subject) =>
            subject.id === payload.subjectId
              ? {
                  ...subject,
                  totalSeconds:
                    subject.totalSeconds + payload.durationSeconds,
                }
              : subject
          )
        );
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : "番茄钟数据保存失败");
        return false;
      } finally {
        setSaving(false);
      }
    },
    [userId]
  );

  const updateCountdownMinutes = useCallback(
    (minutes: number) => {
      const next = clampCountdownMinutes(minutes);
      const updated = { ...preferences, countdownMinutes: next };
      setPreferences(updated);
      setTimerPreferences(updated);
    },
    [preferences]
  );

  const todaySummary = useMemo(() => {
    const todayStart = new Date();
    todayStart.setHours(0, 0, 0, 0);
    const startMs = todayStart.getTime();
    const totalSeconds = sessions
      .filter((s) => new Date(s.startedAt).getTime() >= startMs)
      .reduce((sum, s) => sum + s.durationSeconds, 0);
    return totalSeconds;
  }, [sessions]);

  return {
    status,
    userId,
    subjects,
    sessions,
    preferences,
    error,
    saving,
    todaySummary,
    loadData,
    addSubject,
    removeSubject,
    recordSession,
    updateCountdownMinutes,
  };
}
