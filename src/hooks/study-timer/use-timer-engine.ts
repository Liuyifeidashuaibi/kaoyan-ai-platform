"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { TIMER_DISPLAY_TICK_MS } from "@/lib/study-timer/constants";
import type {
  TimerEngineState,
  TimerMode,
  TimerStatus,
  UseTimerEngineOptions,
} from "@/types/study-timer";

interface TimerEngineInternalState {
  status: TimerStatus;
  /** 当前会话开始前已累积的毫秒（不含当前 running 段） */
  accumulatedMs: number;
  /** 当前 running 段的起始 performance.now */
  runningStartedAt: number | null;
  /** 倒计时目标毫秒 */
  countdownTargetMs: number;
}

const INITIAL_INTERNAL: TimerEngineInternalState = {
  status: "idle",
  accumulatedMs: 0,
  runningStartedAt: null,
  countdownTargetMs: 0,
};

/** 基于 performance.now 计算当前会话毫秒数，避免 setInterval 漂移 */
function computeSessionElapsedMs(state: TimerEngineInternalState): number {
  if (state.status !== "running" || state.runningStartedAt === null) {
    return state.accumulatedMs;
  }

  return state.accumulatedMs + (performance.now() - state.runningStartedAt);
}

function computeCountdownRemainingMs(
  state: TimerEngineInternalState
): number {
  const elapsed = computeSessionElapsedMs(state);
  return Math.max(0, state.countdownTargetMs - elapsed);
}

function buildPublicState(
  mode: TimerMode,
  internal: TimerEngineInternalState
): TimerEngineState {
  const sessionElapsedMs = computeSessionElapsedMs(internal);
  const sessionElapsedSeconds = Math.floor(sessionElapsedMs / 1000);
  const countdownRemainingSeconds = Math.floor(
    computeCountdownRemainingMs(internal) / 1000
  );

  return {
    status: internal.status,
    mode,
    sessionElapsedSeconds,
    countdownTargetSeconds: Math.floor(internal.countdownTargetMs / 1000),
    countdownRemainingSeconds,
  };
}

/**
 * 高精度计时引擎 Hook
 * - 正向计时：暂停时将当前段入库
 * - 倒计时：结束后触发 onSessionComplete
 */
export function useTimerEngine(options: UseTimerEngineOptions) {
  const { mode, countdownTargetSeconds, onSessionComplete, onError } = options;

  const [internal, setInternal] =
    useState<TimerEngineInternalState>(INITIAL_INTERNAL);
  const [tick, setTick] = useState(0);

  const internalRef = useRef(internal);
  const modeRef = useRef(mode);
  const sessionWallStartRef = useRef<string | null>(null);
  const completingRef = useRef(false);
  const onSessionCompleteRef = useRef(onSessionComplete);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    internalRef.current = internal;
  }, [internal]);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    onSessionCompleteRef.current = onSessionComplete;
  }, [onSessionComplete]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  /** 初始化倒计时目标 */
  useEffect(() => {
    if (mode !== "countdown") {
      return;
    }

    setInternal((prev) => ({
      ...prev,
      countdownTargetMs: countdownTargetSeconds * 1000,
      accumulatedMs: 0,
      runningStartedAt: null,
      status: "idle",
    }));
    sessionWallStartRef.current = null;
  }, [mode, countdownTargetSeconds]);

  /** 展示层 tick：仅驱动 UI 重渲染，不参与真实计时 */
  useEffect(() => {
    if (internal.status !== "running") {
      return;
    }

    const timerId = window.setInterval(() => {
      setTick((value) => value + 1);
    }, TIMER_DISPLAY_TICK_MS);

    return () => window.clearInterval(timerId);
  }, [internal.status]);

  const finalizeCountdown = useCallback(async () => {
    if (completingRef.current) {
      return;
    }

    completingRef.current = true;

    const endedAt = new Date().toISOString();
    const startedAt =
      sessionWallStartRef.current ??
      new Date(Date.now() - countdownTargetSeconds * 1000).toISOString();

    try {
      await onSessionCompleteRef.current({
        durationSeconds: countdownTargetSeconds,
        startedAt,
        endedAt,
      });
    } catch (error) {
      onErrorRef.current(
        error instanceof Error ? error.message : "倒计时完成保存失败"
      );
    } finally {
      completingRef.current = false;
      sessionWallStartRef.current = null;
      setInternal({
        status: "completed",
        accumulatedMs: countdownTargetSeconds * 1000,
        runningStartedAt: null,
        countdownTargetMs: countdownTargetSeconds * 1000,
      });
    }
  }, [countdownTargetSeconds]);

  /** 检测倒计时是否结束 */
  useEffect(() => {
    if (modeRef.current !== "countdown" || internal.status !== "running") {
      return;
    }

    const remaining = computeCountdownRemainingMs(internalRef.current);
    if (remaining <= 0) {
      void finalizeCountdown();
    }
  }, [tick, internal.status, finalizeCountdown]);

  const start = useCallback(() => {
    setInternal((prev) => {
      if (prev.status === "running") {
        return prev;
      }

      if (prev.status === "completed") {
        return {
          ...INITIAL_INTERNAL,
          countdownTargetMs:
            modeRef.current === "countdown"
              ? countdownTargetSeconds * 1000
              : 0,
          status: "running",
          runningStartedAt: performance.now(),
        };
      }

      if (!sessionWallStartRef.current) {
        sessionWallStartRef.current = new Date().toISOString();
      }

      return {
        ...prev,
        status: "running",
        runningStartedAt: performance.now(),
      };
    });
  }, [countdownTargetSeconds]);

  const pause = useCallback(() => {
    const snapshot = internalRef.current;
    if (snapshot.status !== "running" || snapshot.runningStartedAt === null) {
      return;
    }

    const elapsedMs = computeSessionElapsedMs(snapshot);

    setInternal({
      ...snapshot,
      status: "paused",
      accumulatedMs: elapsedMs,
      runningStartedAt: null,
    });
  }, []);

  /** 正向计时：将当前会话写入存储（页面离开或手动触发） */
  const flushSession = useCallback(async () => {
    if (modeRef.current !== "stopwatch") {
      return;
    }

    const snapshot = internalRef.current;
    const elapsedMs =
      snapshot.status === "running" && snapshot.runningStartedAt !== null
        ? computeSessionElapsedMs(snapshot)
        : snapshot.accumulatedMs;

    const elapsedSeconds = Math.floor(elapsedMs / 1000);

    if (elapsedSeconds <= 0) {
      return;
    }

    const startedAt =
      sessionWallStartRef.current ??
      new Date(Date.now() - elapsedSeconds * 1000).toISOString();
    const endedAt = new Date().toISOString();

    try {
      await onSessionCompleteRef.current({
        durationSeconds: elapsedSeconds,
        startedAt,
        endedAt,
      });
      sessionWallStartRef.current = null;
      setInternal({
        status: "idle",
        accumulatedMs: 0,
        runningStartedAt: null,
        countdownTargetMs: 0,
      });
    } catch (error) {
      onErrorRef.current(
        error instanceof Error ? error.message : "保存学习时长失败"
      );
    }
  }, []);

  const reset = useCallback(() => {
    sessionWallStartRef.current = null;
    completingRef.current = false;
    setInternal({
      ...INITIAL_INTERNAL,
      countdownTargetMs:
        modeRef.current === "countdown" ? countdownTargetSeconds * 1000 : 0,
    });
  }, [countdownTargetSeconds]);

  const publicState = useMemo(
    () => buildPublicState(mode, internal),
    [mode, internal, tick]
  );

  return {
    state: publicState,
    start,
    pause,
    reset,
    flushSession,
  };
}
