"use client";

import { useCallback, useMemo, useState } from "react";

import {
  addSubjectToStorage,
  appendStudyRecord,
  getTomatoStorage,
  removeSubjectFromStorage,
  setTomatoStorage,
} from "@/components/TomatoClock/storage";
import type { TomatoStorage } from "@/components/TomatoClock/types";

export function useTomatoStorage() {
  const [storage, setStorageState] = useState<TomatoStorage | null>(() => {
    if (typeof window === "undefined") {
      return null;
    }
    return getTomatoStorage();
  });
  const [error, setError] = useState<string | null>(null);

  const updateStorage = useCallback((next: TomatoStorage) => {
    if (!setTomatoStorage(next)) {
      setError("番茄钟数据保存失败，请检查浏览器存储权限");
      return false;
    }
    setStorageState(next);
    setError(null);
    return true;
  }, []);

  const subjects = useMemo(
    () =>
      storage
        ? [...storage.subjects].sort((a, b) => a.sortOrder - b.sortOrder)
        : [],
    [storage]
  );

  const addSubject = useCallback(
    (name: string): string | null => {
      if (!storage) {
        return null;
      }
      const result = addSubjectToStorage(storage, name);
      if ("error" in result) {
        setError(result.error);
        return null;
      }
      updateStorage(result.storage);
      return result.subject.id;
    },
    [storage, updateStorage]
  );

  const removeSubject = useCallback(
    (subjectId: string) => {
      if (!storage) {
        return false;
      }
      updateStorage(removeSubjectFromStorage(storage, subjectId));
      return true;
    },
    [storage, updateStorage]
  );

  const saveSession = useCallback(
    (subjectId: string, durationSeconds: number) => {
      if (!storage || durationSeconds <= 0) {
        return false;
      }
      const subject = storage.subjects.find((item) => item.id === subjectId);
      if (!subject) {
        return false;
      }
      return updateStorage(
        appendStudyRecord(storage, {
          subjectId,
          subjectName: subject.name,
          durationSeconds,
        })
      );
    },
    [storage, updateStorage]
  );

  const updateCountdownMinutes = useCallback(
    (minutes: number) => {
      if (!storage) {
        return;
      }
      updateStorage({ ...storage, countdownMinutes: minutes });
    },
    [storage, updateStorage]
  );

  return {
    storage,
    subjects,
    error,
    setError,
    addSubject,
    removeSubject,
    saveSession,
    updateCountdownMinutes,
  };
}
