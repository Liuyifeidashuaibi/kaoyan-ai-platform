"use client";

import Link from "next/link";
import { BarChart3 } from "lucide-react";

import { SubjectSection } from "@/components/TomatoClock/SubjectSection";
import { TimerSection } from "@/components/TomatoClock/TimerSection";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useTomatoStorage } from "@/hooks/use-tomato-storage";
import { useCallback, useState } from "react";

export function TomatoClock() {
  const {
    storage,
    subjects,
    error,
    addSubject,
    removeSubject,
    saveSession,
    updateCountdownMinutes,
  } = useTomatoStorage();

  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(
    null
  );
  const [timerActive, setTimerActive] = useState(false);

  const handleAddSubject = useCallback(
    (name: string) => {
      const subjectId = addSubject(name);
      if (subjectId) {
        setSelectedSubjectId(subjectId);
        return true;
      }
      return false;
    },
    [addSubject]
  );

  const handleRemoveSubject = useCallback(
    (subjectId: string) => {
      if (timerActive) {
        return;
      }
      removeSubject(subjectId);
      if (selectedSubjectId === subjectId) {
        setSelectedSubjectId(
          subjects.find((item) => item.id !== subjectId)?.id ?? null
        );
      }
    },
    [removeSubject, selectedSubjectId, subjects, timerActive]
  );

  if (!storage) {
    return (
      <div className="p-8 text-sm text-muted-foreground">番茄钟加载中…</div>
    );
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Timer</h1>
          <p className="text-muted-foreground">
            专注计时，数据永久保存在本地
          </p>
        </div>
        <Link href="/study/tomato/stats">
          <Button type="button" variant="outline">
            <BarChart3 className="size-4" />
            番茄钟统计
          </Button>
        </Link>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <SubjectSection
        subjects={subjects}
        selectedSubjectId={selectedSubjectId}
        subjectLocked={timerActive}
        onSelect={setSelectedSubjectId}
        onAdd={handleAddSubject}
        onRemove={handleRemoveSubject}
      />

      <TimerSection
        key={storage.countdownMinutes}
        subjects={subjects}
        selectedSubjectId={selectedSubjectId}
        countdownMinutes={storage.countdownMinutes}
        onCountdownMinutesChange={updateCountdownMinutes}
        onSessionSave={saveSession}
        onActiveChange={setTimerActive}
      />
    </div>
  );
}
