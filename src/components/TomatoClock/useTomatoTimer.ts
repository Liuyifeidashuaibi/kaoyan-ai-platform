"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { formatMmSs } from "@/components/TomatoClock/utils";
import type {
  TimerMode,
  TimerRunStatus,
  TomatoTimerState,
} from "@/components/TomatoClock/types";

interface TimerInternalState {
  status: TimerRunStatus;
  accumulatedMs: number;
  runningStartedAt: number | null;
}

const INITIAL: TimerInternalState = {
  status: "idle",
  accumulatedMs: 0,
  runningStartedAt: null,
};

function computeElapsedMs(state: TimerInternalState): number {
  if (state.status !== "running" || state.runningStartedAt === null) {
    return state.accumulatedMs;
  }
  return state.accumulatedMs + (performance.now() - state.runningStartedAt);
}

interface UseTomatoTimerOptions {
  mode: TimerMode;
  /** 倒计时总秒数 */
  countdownSeconds: number;
  onCountdownComplete: () => void;
  onCountupPauseSave: (elapsedSeconds: number) => void;
}

export function useTomatoTimer(options: UseTomatoTimerOptions) {
  const { mode, countdownSeconds, onCountdownComplete, onCountupPauseSave } =
    options;

  const [internal, setInternal] = useState<TimerInternalState>(INITIAL);
  const [tick, setTick] = useState(0);

  const internalRef = useRef(internal);
  const wallStartRef = useRef<string | null>(null);
  const onCountdownCompleteRef = useRef(onCountdownComplete);
  const onCountupPauseSaveRef = useRef(onCountupPauseSave);

  useEffect(() => {
    internalRef.current = internal;
  }, [internal]);

  useEffect(() => {
    onCountdownCompleteRef.current = onCountdownComplete;
  }, [onCountdownComplete]);

  useEffect(() => {
    onCountupPauseSaveRef.current = onCountupPauseSave;
  }, [onCountupPauseSave]);

  useEffect(() => {
    if (internal.status !== "running") {
      return;
    }

    let frameId = 0;

    const loop = () => {
      const snapshot = internalRef.current;
      const elapsedMs = computeElapsedMs(snapshot);

      if (mode === "countdown") {
        const remainingMs = countdownSeconds * 1000 - elapsedMs;
        if (remainingMs <= 0) {
          onCountdownCompleteRef.current();
          wallStartRef.current = null;
          setInternal(INITIAL);
          return;
        }
      }

      setTick((value) => value + 1);
      frameId = window.requestAnimationFrame(loop);
    };

    frameId = window.requestAnimationFrame(loop);
    return () => window.cancelAnimationFrame(frameId);
  }, [countdownSeconds, internal.status, mode]);

  const publicState = useMemo<TomatoTimerState>(() => {
    const elapsedMs = computeElapsedMs(internal);
    const elapsedSeconds = Math.floor(elapsedMs / 1000);

    if (mode === "countup") {
      return {
        mode,
        status: internal.status,
        displayTime: formatMmSs(elapsedSeconds),
        elapsedSeconds,
        remainingSeconds: 0,
        totalSeconds: 0,
      };
    }

    const remainingSeconds = Math.max(
      0,
      Math.ceil((countdownSeconds * 1000 - elapsedMs) / 1000)
    );

    return {
      mode,
      status: internal.status,
      displayTime: formatMmSs(remainingSeconds),
      elapsedSeconds,
      remainingSeconds,
      totalSeconds: countdownSeconds,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- tick drives live updates
  }, [countdownSeconds, internal, mode, tick]);

  const isActive = internal.status !== "idle";

  const start = useCallback(() => {
    setInternal((prev) => {
      if (prev.status === "running") {
        return prev;
      }

      if (!wallStartRef.current) {
        wallStartRef.current = new Date().toISOString();
      }

      return {
        ...prev,
        status: "running",
        runningStartedAt: performance.now(),
      };
    });
  }, []);

  const pause = useCallback(() => {
    const snapshot = internalRef.current;
    if (snapshot.status !== "running" || snapshot.runningStartedAt === null) {
      return;
    }

    const elapsedMs = computeElapsedMs(snapshot);
    const elapsedSeconds = Math.floor(elapsedMs / 1000);

    if (mode === "countup" && elapsedSeconds > 0) {
      onCountupPauseSaveRef.current(elapsedSeconds);
      wallStartRef.current = null;
      setInternal(INITIAL);
      return;
    }

    setInternal({
      status: "paused",
      accumulatedMs: elapsedMs,
      runningStartedAt: null,
    });
  }, [mode]);

  const reset = useCallback(() => {
    wallStartRef.current = null;
    setInternal(INITIAL);
  }, []);

  const flushOnUnmount = useCallback(() => {
    const snapshot = internalRef.current;
    if (
      mode !== "countup" ||
      snapshot.status !== "running" ||
      snapshot.runningStartedAt === null
    ) {
      return;
    }

    const elapsedSeconds = Math.floor(computeElapsedMs(snapshot) / 1000);
    if (elapsedSeconds > 0) {
      onCountupPauseSaveRef.current(elapsedSeconds);
    }
  }, [mode]);

  return {
    state: publicState,
    isActive,
    start,
    pause,
    reset,
    flushOnUnmount,
  };
}
