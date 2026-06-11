"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { BarChart3, Loader2 } from "lucide-react";

import { DailySummary } from "@/app/(main)/timer/_components/daily-summary";
import { SubjectSection } from "@/app/(main)/timer/_components/subject-section";
import { TimerSection } from "@/app/(main)/timer/_components/timer-section";
import { useTimerData } from "@/app/(main)/timer/_hooks/use-timer-data";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export function TomatoClock() {
  const {
    status,
    subjects,
    preferences,
    error,
    saving,
    todaySummary,
    loadData,
    addSubject,
    removeSubject,
    recordSession,
    updateCountdownMinutes,
  } = useTimerData();

  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(
    null
  );
  const [timerActive, setTimerActive] = useState(false);

  const handleAddSubject = useCallback(
    async (name: string) => {
      const subjectId = await addSubject(name);
      if (subjectId) {
        setSelectedSubjectId(subjectId);
      }
      return subjectId;
    },
    [addSubject]
  );

  const handleRemoveSubject = useCallback(
    async (subjectId: string) => {
      if (timerActive) {
        return false;
      }
      const ok = await removeSubject(subjectId);
      if (ok && selectedSubjectId === subjectId) {
        setSelectedSubjectId(
          subjects.find((item) => item.id !== subjectId)?.id ?? null
        );
      }
      return ok;
    },
    [removeSubject, selectedSubjectId, subjects, timerActive]
  );

  if (status === "loading") {
    return (
      <div className="flex items-center justify-center gap-2 p-12 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        番茄钟加载中…
      </div>
    );
  }

  if (status === "unconfigured") {
    return (
      <Alert variant="destructive" className="max-w-2xl">
        <AlertDescription>
          Supabase 未配置，番茄钟无法保存数据。请配置环境变量后刷新页面。
        </AlertDescription>
      </Alert>
    );
  }

  if (status === "unauthenticated") {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4">
        <Alert>
          <AlertDescription>
            登录后即可使用番茄钟，学习数据将保存到云端，刷新页面不丢失。
          </AlertDescription>
        </Alert>
        <Link href="/login?next=/timer">
          <Button type="button">前往登录</Button>
        </Link>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4">
        <Alert variant="destructive">
          <AlertDescription>{error ?? "番茄钟数据加载失败"}</AlertDescription>
        </Alert>
        <Button type="button" variant="outline" onClick={() => void loadData()}>
          重新加载
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">番茄钟</h1>
          <p className="text-muted-foreground">
            专注计时，数据保存在云端
          </p>
        </div>
        <Link href="/timer/stats">
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

      <DailySummary todaySeconds={todaySummary} />

      <SubjectSection
        subjects={subjects}
        selectedSubjectId={selectedSubjectId}
        subjectLocked={timerActive}
        saving={saving}
        onSelect={setSelectedSubjectId}
        onAdd={handleAddSubject}
        onRemove={handleRemoveSubject}
      />

      <TimerSection
        key={preferences.countdownMinutes}
        subjects={subjects}
        selectedSubjectId={selectedSubjectId}
        countdownMinutes={preferences.countdownMinutes}
        saving={saving}
        onCountdownMinutesChange={updateCountdownMinutes}
        onSessionSave={recordSession}
        onActiveChange={setTimerActive}
      />
    </div>
  );
}
