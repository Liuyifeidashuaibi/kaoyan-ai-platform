"use client";

import { useEffect, useState } from "react";

import { ConfirmDialog } from "@/components/TomatoClock/ConfirmDialog";
import { useTomatoTimer } from "@/components/TomatoClock/useTomatoTimer";
import { clampCountdownMinutes } from "@/components/TomatoClock/storage";
import type { Subject, TimerMode } from "@/components/TomatoClock/types";
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
  subjects: Subject[];
  selectedSubjectId: string | null;
  countdownMinutes: number;
  onCountdownMinutesChange: (minutes: number) => void;
  onSessionSave: (subjectId: string, durationSeconds: number) => void;
  onActiveChange: (active: boolean) => void;
}

export function TimerSection({
  subjects,
  selectedSubjectId,
  countdownMinutes,
  onCountdownMinutesChange,
  onSessionSave,
  onActiveChange,
}: TimerSectionProps) {
  const [mode, setMode] = useState<TimerMode>("countup");
  const [lockedSubjectId, setLockedSubjectId] = useState<string | null>(null);
  const [resetOpen, setResetOpen] = useState(false);
  const [minutesDraft, setMinutesDraft] = useState(String(countdownMinutes));

  const countdownSeconds = countdownMinutes * 60;

  const saveSession = (durationSeconds: number) => {
    const subjectId = lockedSubjectId ?? selectedSubjectId;
    if (!subjectId || durationSeconds <= 0) {
      return;
    }
    onSessionSave(subjectId, durationSeconds);
    setLockedSubjectId(null);
    onActiveChange(false);
  };

  const { state, isActive, start, pause, reset, flushOnUnmount } =
    useTomatoTimer({
      mode,
      countdownSeconds,
      onCountdownComplete: () => saveSession(countdownSeconds),
      onCountupPauseSave: (elapsedSeconds) => saveSession(elapsedSeconds),
    });

  useEffect(() => {
    return () => {
      flushOnUnmount();
    };
  }, [flushOnUnmount]);

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
    state.status !== "running";
  const canPause = state.status === "running";
  const canReset = state.status !== "idle";

  const handleStart = () => {
    if (!selectedSubjectId) {
      return;
    }
    setLockedSubjectId(selectedSubjectId);
    onActiveChange(true);
    start();
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
                disabled={isActive}
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
              正计时从 00:00 累计，暂停后自动保存到当前科目
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
          </div>

          <div className="flex flex-wrap justify-center gap-3">
            {canStart ? (
              <Button type="button" onClick={handleStart}>
                {state.status === "paused" ? "继续" : "开始"}
              </Button>
            ) : null}
            {canPause ? (
              <Button type="button" variant="secondary" onClick={() => pause()}>
                {mode === "countup" ? "暂停并保存" : "暂停"}
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
