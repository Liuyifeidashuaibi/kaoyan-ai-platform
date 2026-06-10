"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createStudySubject,
  fetchStudySubjects,
} from "@/lib/study-timer/repository";
import { formatDurationZh } from "@/lib/study-timer/utils";
import type {
  CreateStudySubjectInput,
  StudySubject,
  SubjectStatItem,
} from "@/types/study-timer";

interface UseStudySubjectsState {
  subjects: StudySubject[];
  loading: boolean;
  error: string | null;
  notice: string | null;
}

export function useStudySubjects() {
  const [state, setState] = useState<UseStudySubjectsState>({
    subjects: [],
    loading: true,
    error: null,
    notice: null,
  });

  const loadSubjects = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));

    const result = await fetchStudySubjects();

    setState({
      subjects: result.data ?? [],
      loading: false,
      error: result.error,
      notice: result.error?.includes("降级") ? result.error : null,
    });
  }, []);

  useEffect(() => {
    void loadSubjects();
  }, [loadSubjects]);

  const createSubject = useCallback(
    async (input: CreateStudySubjectInput) => {
      setState((prev) => ({ ...prev, error: null, notice: null }));

      const result = await createStudySubject(input);

      if (result.error || !result.data) {
        setState((prev) => ({
          ...prev,
          error: result.error ?? "创建科目失败",
        }));
        return null;
      }

      setState((prev) => ({
        ...prev,
        subjects: [result.data as StudySubject, ...prev.subjects],
      }));

      return result.data;
    },
    []
  );

  const stats = useMemo<SubjectStatItem[]>(() => {
    const totalSeconds = state.subjects.reduce(
      (sum, subject) => sum + subject.totalSeconds,
      0
    );

    return state.subjects.map((subject) => ({
      subject,
      formattedDuration: formatDurationZh(subject.totalSeconds),
      percentage:
        totalSeconds > 0
          ? Math.round((subject.totalSeconds / totalSeconds) * 1000) / 10
          : 0,
    }));
  }, [state.subjects]);

  const totalSeconds = useMemo(
    () => state.subjects.reduce((sum, subject) => sum + subject.totalSeconds, 0),
    [state.subjects]
  );

  return {
    subjects: state.subjects,
    stats,
    totalSeconds,
    loading: state.loading,
    error: state.error,
    notice: state.notice,
    reload: loadSubjects,
    createSubject,
  };
}
