"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { CountdownConfigPanel } from "@/components/study-timer/countdown-config-panel";
import { ResetConfirmDialog } from "@/components/study-timer/reset-confirm-dialog";
import { TimerControls } from "@/components/study-timer/timer-controls";
import { TimerDisplay } from "@/components/study-timer/timer-display";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useTimerEngine } from "@/hooks/study-timer/use-timer-engine";
import { useTimerNotification } from "@/hooks/study-timer/use-timer-notification";
import {
  fetchStudySubjectById,
  persistStudySession,
} from "@/lib/study-timer/repository";
import { formatDurationZh, minutesToSeconds } from "@/lib/study-timer/utils";
import type { StudySubject, TimerMode } from "@/types/study-timer";
import { COUNTDOWN_PRESETS_MINUTES } from "@/lib/study-timer/constants";

interface SubjectTimerPageProps {
  subjectId: string;
}

export function SubjectTimerPage({ subjectId }: SubjectTimerPageProps) {
  const [subject, setSubject] = useState<StudySubject | null>(null);
  const [loadingSubject, setLoadingSubject] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [persistNotice, setPersistNotice] = useState<string | null>(null);
  const [persistError, setPersistError] = useState<string | null>(null);
  const [mode, setMode] = useState<TimerMode>("stopwatch");
  const [countdownMinutes, setCountdownMinutes] = useState<number>(
    COUNTDOWN_PRESETS_MINUTES[1]
  );
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [completeBanner, setCompleteBanner] = useState(false);

  const { notifyComplete } = useTimerNotification();

  const countdownTargetSeconds = useMemo(
    () => minutesToSeconds(countdownMinutes),
    [countdownMinutes]
  );

  const handleSessionComplete = useCallback(
    async (payload: {
      durationSeconds: number;
      startedAt: string;
      endedAt: string;
    }) => {
      const result = await persistStudySession({
        subjectId,
        mode,
        durationSeconds: payload.durationSeconds,
        startedAt: payload.startedAt,
        endedAt: payload.endedAt,
      });

      if (result.error) {
        setPersistError(result.error);
      } else if (result.data) {
        setPersistNotice("学习时长已保存");
        setSubject(result.data);
      }

      if (mode === "countdown") {
        setCompleteBanner(true);
        notifyComplete(subject?.name ?? "当前科目");
      }
    },
    [subjectId, mode, notifyComplete, subject?.name]
  );

  const handleEngineError = useCallback((message: string) => {
    setPersistError(message);
  }, []);

  const { state, start, pause, reset, flushSession } = useTimerEngine({
    mode,
    countdownTargetSeconds,
    onSessionComplete: handleSessionComplete,
    onError: handleEngineError,
  });

  useEffect(() => {
    async function loadSubject() {
      setLoadingSubject(true);
      setLoadError(null);

      const result = await fetchStudySubjectById(subjectId);

      setLoadingSubject(false);

      if (result.error || !result.data) {
        setLoadError(result.error ?? "科目不存在");
        return;
      }

      setSubject(result.data);
    }

    void loadSubject();
  }, [subjectId]);

  useEffect(() => {
    return () => {
      void flushSession();
    };
  }, [flushSession]);

  const displaySeconds = useMemo(() => {
    if (mode === "countdown") {
      return state.countdownRemainingSeconds;
    }
    return state.sessionElapsedSeconds;
  }, [mode, state.countdownRemainingSeconds, state.sessionElapsedSeconds]);

  const isRunning = state.status === "running";
  const canConfigureCountdown = mode === "countdown" && state.status === "idle";

  const handleResetConfirm = useCallback(() => {
    reset();
    setResetDialogOpen(false);
    setCompleteBanner(false);
    setPersistError(null);
  }, [reset]);

  if (loadingSubject) {
    return (
      <div className="p-8 text-sm text-muted-foreground">加载科目信息…</div>
    );
  }

  if (loadError || !subject) {
    return (
      <div className="flex flex-col gap-4 p-8">
        <Alert variant="destructive">
          <AlertDescription>{loadError ?? "科目不存在"}</AlertDescription>
        </Alert>
        <Link href="/pomodoro" className="text-sm text-primary underline-offset-4 hover:underline">
          返回科目列表
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <span
            className="size-4 rounded-full"
            style={{ backgroundColor: subject.color }}
            aria-hidden
          />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{subject.name}</h1>
            <p className="text-sm text-muted-foreground">
              累计 {formatDurationZh(subject.totalSeconds)}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Badge variant={isRunning ? "default" : "secondary"}>
            {state.status === "running"
              ? "计时中"
              : state.status === "paused"
                ? "已暂停"
                : state.status === "completed"
                  ? "已完成"
                  : "待开始"}
          </Badge>
          <Link
            href="/pomodoro"
            className="text-sm text-primary underline-offset-4 hover:underline"
          >
            返回列表
          </Link>
        </div>
      </div>

      {completeBanner ? (
        <Alert>
          <AlertDescription>
            倒计时结束！本次 {countdownMinutes} 分钟已计入科目总时长。
          </AlertDescription>
        </Alert>
      ) : null}

      {persistNotice ? (
        <Alert>
          <AlertDescription>{persistNotice}</AlertDescription>
        </Alert>
      ) : null}

      {persistError ? (
        <Alert variant="destructive">
          <AlertDescription>{persistError}</AlertDescription>
        </Alert>
      ) : null}

      <Tabs
        value={mode}
        onValueChange={(value) => {
          if (isRunning) {
            return;
          }
          setMode(value as TimerMode);
          reset();
          setCompleteBanner(false);
        }}
      >
        <TabsList>
          <TabsTrigger value="stopwatch" disabled={isRunning}>
            正向计时
          </TabsTrigger>
          <TabsTrigger value="countdown" disabled={isRunning}>
            倒计时
          </TabsTrigger>
        </TabsList>

        <TabsContent value="stopwatch" className="mt-6 space-y-6">
          <TimerDisplay
            label="本次学习"
            seconds={displaySeconds}
            accentColor={subject.color}
          />
        </TabsContent>

        <TabsContent value="countdown" className="mt-6 space-y-6">
          {canConfigureCountdown ? (
            <CountdownConfigPanel
              minutes={countdownMinutes}
              onChange={setCountdownMinutes}
            />
          ) : null}
          <TimerDisplay
            label="剩余时间"
            seconds={displaySeconds}
            accentColor={subject.color}
          />
        </TabsContent>
      </Tabs>

      <TimerControls
        isRunning={isRunning}
        onStart={() => start()}
        onPause={() => pause()}
        onReset={() => setResetDialogOpen(true)}
      />

      <ResetConfirmDialog
        open={resetDialogOpen}
        onOpenChange={setResetDialogOpen}
        onConfirm={handleResetConfirm}
      />
    </div>
  );
}
