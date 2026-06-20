"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";

import { SubjectManager } from "./subject-manager";
import { TimerControls } from "./timer-controls";
import { TimerGate } from "./timer-gate";
import type { TimerMode } from "./types";
import { useTimerData } from "./use-timer-data";
import { useTimerEngine } from "./use-timer-engine";
import { clampCountdownMinutes, formatMmSs } from "./utils";

export function TimerPage() {
  const {
    status,
    subjects,
    error,
    saving,
    loadData,
    addSubject,
    recordSession,
  } = useTimerData();

  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(null);
  const [mode, setMode] = useState<TimerMode>("countdown");
  const [countdownMinutes, setCountdownMinutes] = useState(50);

  useEffect(() => {
    if (subjects.length > 0 && !selectedSubjectId) {
      setSelectedSubjectId(subjects[0].id);
    }
  }, [selectedSubjectId, subjects]);

  const selectedSubject =
    subjects.find((subject) => subject.id === selectedSubjectId) ?? null;

  const countdownSeconds = countdownMinutes * 60;

  const engine = useTimerEngine({
    mode,
    countdownSeconds,
  });

  const idleDisplayTime =
    mode === "countdown" ? formatMmSs(countdownSeconds) : "00:00";

  const displayTime = engine.isActive ? engine.displayTime : idleDisplayTime;

  const handleStart = useCallback(() => {
    if (!selectedSubjectId) return;
    engine.start();
  }, [engine, selectedSubjectId]);

  const handleEnd = useCallback(async () => {
    if (!selectedSubject) return;

    const elapsedSeconds = engine.getElapsedSeconds();
    const startedAt = engine.getSessionStartedAt();

    if (elapsedSeconds > 0 && startedAt) {
      await recordSession({
        subjectId: selectedSubject.id,
        subjectName: selectedSubject.name,
        mode: mode === "stopwatch" ? "stopwatch" : "countdown",
        durationSeconds: elapsedSeconds,
        startedAt,
      });
    }

    engine.clearSession();
  }, [engine, mode, recordSession, selectedSubject]);

  return (
    <TimerGate
      status={status}
      error={error}
      title="Timer"
      loginNext="/study/tomato"
      onRetry={() => void loadData()}
    >
      <div className="mx-auto flex w-full max-w-xl flex-col justify-center gap-4 px-4 py-4 pb-8 sm:gap-5 sm:px-6 sm:py-6 md:min-h-[calc(100dvh-1rem)]">
        <header className="flex shrink-0 items-center justify-between gap-4">
          <h1 className="text-xl font-semibold tracking-tight text-neutral-900 sm:text-2xl">
            Timer
          </h1>
          <Link
            href="/study/tomato/statistics"
            className="inline-flex items-center gap-1 text-sm font-medium text-[#3B82F6] transition-colors hover:text-[#2563EB]"
          >
            View Statistics
            <ArrowRight className="size-4" />
          </Link>
        </header>

        <SubjectManager
          subjects={subjects}
          selectedId={selectedSubjectId}
          onSelect={setSelectedSubjectId}
          onAdd={addSubject}
          disabled={engine.isActive}
          saving={saving}
        />

        <TimerControls
          mode={mode}
          onModeChange={setMode}
          countdownMinutes={countdownMinutes}
          onCountdownMinutesChange={(value) =>
            setCountdownMinutes(clampCountdownMinutes(value))
          }
          subjects={subjects}
          selectedSubject={selectedSubject}
          displayTime={displayTime}
          progress={engine.progress}
          status={engine.status}
          isActive={engine.isActive}
          saving={saving}
          onStart={handleStart}
          onPause={engine.pause}
          onEnd={() => void handleEnd()}
        />

        {error && (
          <p className="text-center text-sm text-red-500">{error}</p>
        )}
      </div>
    </TimerGate>
  );
}
