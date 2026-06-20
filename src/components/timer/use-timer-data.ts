"use client";

import { useCallback, useEffect, useState } from "react";

import {
  createSubject,
  fetchTimerData,
  getCurrentUserId,
  saveTimerSession,
} from "@/app/(main)/timer/_lib/repository";
import type { TimerSession, TimerSubject } from "./types";
import { isSupabaseConfigured } from "@/lib/supabase/client";

type LoadStatus = "loading" | "ready" | "error" | "unauthenticated" | "unconfigured";

export function useTimerData() {
  const [status, setStatus] = useState<LoadStatus>("loading");
  const [userId, setUserId] = useState<string | null>(null);
  const [subjects, setSubjects] = useState<TimerSubject[]>([]);
  const [sessions, setSessions] = useState<TimerSession[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const loadData = useCallback(async () => {
    if (!isSupabaseConfigured()) {
      setStatus("unconfigured");
      setError("Supabase is not configured. Cannot save study records");
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
      setError(err instanceof Error ? err.message : "Failed to load data");
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const addSubject = useCallback(
    async (name: string): Promise<string | null> => {
      if (!userId) return null;

      setSaving(true);
      setError(null);

      try {
        const subject = await createSubject(userId, name, subjects.length);
        setSubjects((prev) => [...prev, subject]);
        return subject.id;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to add subject");
        return null;
      } finally {
        setSaving(false);
      }
    },
    [subjects.length, userId]
  );

  const recordSession = useCallback(
    async (payload: {
      subjectId: string;
      subjectName: string;
      mode: "stopwatch" | "countdown";
      durationSeconds: number;
      startedAt: string;
    }): Promise<boolean> => {
      if (!userId || payload.durationSeconds <= 0) return false;

      setSaving(true);
      setError(null);
      const endedAt = new Date().toISOString();

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
        setError(err instanceof Error ? err.message : "Failed to save");
        return false;
      } finally {
        setSaving(false);
      }
    },
    [userId]
  );

  return {
    status,
    subjects,
    sessions,
    error,
    saving,
    loadData,
    addSubject,
    recordSession,
  };
}
