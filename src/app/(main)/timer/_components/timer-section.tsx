"use client";

import { useEffect, useState } from "react";

import { ConfirmDialog } from "@/app/(main)/timer/_components/confirm-dialog";
import { useTimerEngine } from "@/app/(main)/timer/_hooks/use-timer-engine";
import type { TimerMode, TimerSubject } from "@/app/(main)/timer/_lib/types";
import { clampCountdownMinutes } from "@/app/(main)/timer/_lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

interface TimerSectionProps {
  subjects: TimerSubject[];
  selectedSubjectId: string | null;
  countdownMinutes: number;
  saving: boolean;
  onCountdownMinutesChange: (minutes: number) => void;
  onSessionSave: (payload: {
    subjectId: string;
    subjectName: string;
    mode: "stopwatch" | "countdown";
    durationSeconds: number;
    startedAt: string;
  }) => Promise<boolean>;
  onActiveChange: (active: boolean) => void;
}

export function TimerSection({
  subjects,
  selectedSubjectId,
  countdownMinutes,
  saving,
  onCountdownMinutesChange,
  onSessionSave,
  onActiveChange,
}: TimerSectionProps) {
  const [mode, setMode] = useState<TimerMode>("countup");
  const [lockedSubjectId, setLockedSubjectId] = useState<string | null>(null);
  const [resetOpen, setResetOpen] = useState(false);
  const [minutesDraft, setMinutesDraft] = useState(String(countdownMinutes));

  const countdownSeconds = countdownMinutes * 60;

  const persistSession = async (durationSeconds: number) => {
    const subjectId = lockedSubjectId ?? selectedSubjectId;
    if (!subjectId || durationSeconds <= 0) {
      return;
    }

    const subject = subjects.find((item) => item.id === subjectId);
    if (!subject) {
      return;
    }

    const startedAt = getSessionStartedAt() ?? new Date().toISOString();
    const ok = await onSessionSave({
      subjectId,
      subjectName: subject.name,
      mode: mode === "countup" ? "stopwatch" : "countdown",
      durationSeconds,
      startedAt,
    });

    if (ok) {
      setLockedSubjectId(null);
      onActiveChange(false);
      reset();
    }
  };

  const {
    state,
    isActive,
    start,
    pause,
    reset,
    getElapsedSeconds,
    getSessionStartedAt,
  } = useTimerEngine({
    mode,
    countdownSeconds,
    onCountdownComplete: () => {
      void persistSession(countdownSeconds);
    },
  });

  useEffect(() => {
    onActiveChange(isActive);
  }, [isActive, onActiveChange]);

  const activeSubject = subjects.find(
    (item) => item.id === (lockedSubjectId ?? selectedSubjectId)
  );

  const canSwitchMode = state.status === "idle";
  const canStart =
    Boolean(lockedSubjectId ?? selectedSubjectId) &&
    Boolean(selectedSubjectId) &&
    state.status !== "running" &&
    !saving;
  const canPause = state.status === "running" && !saving;
  const canStop =
    state.status !== "idle" && getElapsedSeconds() > 0 && !saving;
  const canReset = state.status !== "idle" && !saving;

  const handleStart = () => {
    if (!selectedSubjectId) {
      return;
    }
    setLockedSubjectId(selectedSubjectId);
    onActiveChange(true);
    start();
  };

  const handleStop = () => {
    const elapsed = getElapsedSeconds();
    if (elapsed > 0) {
      void persistSession(elapsed);
    } else {
      reset();
      setLockedSubjectId(null);
      onActiveChange(false);
    }
  };

  const handleReset = () => {
    reset();
    setLockedSubjectId(null);
    onActiveChange(false);
    setResetOpen(false);
  };

  if (!selectedSubjectId) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          请先选择科目，再开始番茄钟计时
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>番茄钟计时</CardTitle>
          <CardDescription>
            支持正计时与倒计时，MM:SS 格式显示
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <Tabs
            value={mode}
            onValueChange={(value) => {
              if (canSwitchMode) {
                setMode(value as TimerMode);
              }
            }}
          >
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="countup" disabled={!canSwitchMode}>
                正计时
              </TabsTrigger>
              <TabsTrigger value="countdown" disabled={!canSwitchMode}>
                倒计时
              </TabsTrigger>
            </TabsList>
          </Tabs>

          {mode === "countdown" ? (
            <div className="space-y-2">
              <Label htmlFor="countdown-minutes">倒计时时长（5-60 分钟）</Label>
              <Input
                id="countdown-minutes"
                type="number"
                min={5}
                max={60}
                value={minutesDraft}
                disabled={isActive || saving}
                onChange={(event) => setMinutesDraft(event.target.value)}
                onBlur={() => {
                  const next = clampCountdownMinutes(Number(minutesDraft) || 25);
                  setMinutesDraft(String(next));
                  onCountdownMinutesChange(next);
                }}
              />
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              正计时从 00:00 累计，停止后保存到当前科目
            </p>
          )}

          <div className="rounded-xl border border-border bg-muted/30 px-4 py-10 text-center">
            <p
              className={cn(
                "font-mono text-5xl font-bold tabular-nums sm:text-6xl",
                state.status === "running" && "text-primary"
              )}
            >
              {state.displayTime}
            </p>
            {activeSubject ? (
              <p className="mt-3 text-sm text-muted-foreground">
                当前科目：{activeSubject.name}
              </p>
            ) : null}
            {isActive ? (
              <p className="mt-1 text-xs text-amber-600">
                计时进行中，无法切换科目
              </p>
            ) : null}
            {saving ? (
              <p className="mt-1 text-xs text-muted-foreground">
                番茄钟数据保存中…
              </p>
            ) : null}
          </div>

          <div className="flex flex-wrap justify-center gap-3">
            {canStart ? (
              <Button type="button" onClick={handleStart}>
                {state.status === "paused" ? "继续" : "开始"}
              </Button>
            ) : null}
            {canPause ? (
              <Button type="button" variant="secondary" onClick={() => pause()}>
                暂停
              </Button>
            ) : null}
            {canStop ? (
              <Button type="button" onClick={handleStop}>
                停止
              </Button>
            ) : null}
            {canReset ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => setResetOpen(true)}
              >
                重置
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <ConfirmDialog
        open={resetOpen}
        title="确认重置番茄钟？"
        description="重置后将丢弃当前计时进度，不会保存到统计。"
        confirmLabel="确认重置"
        onOpenChange={setResetOpen}
        onConfirm={handleReset}
      />
    </>
  );
}
