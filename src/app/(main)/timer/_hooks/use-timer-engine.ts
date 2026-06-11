"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { TimerMode, TimerRunStatus, TimerState } from "@/app/(main)/timer/_lib/types";
import { formatMmSs } from "@/app/(main)/timer/_lib/utils";

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

interface UseTimerEngineOptions {
  mode: TimerMode;
  countdownSeconds: number;
  onCountdownComplete: () => void;
}

export function useTimerEngine(options: UseTimerEngineOptions) {
  const { mode, countdownSeconds, onCountdownComplete } = options;

  const [internal, setInternal] = useState<TimerInternalState>(INITIAL);
  const [tick, setTick] = useState(0);
  const sessionStartedAtRef = useRef<string | null>(null);

  const internalRef = useRef(internal);
  const onCountdownCompleteRef = useRef(onCountdownComplete);

  useEffect(() => {
    internalRef.current = internal;
  }, [internal]);

  useEffect(() => {
    onCountdownCompleteRef.current = onCountdownComplete;
  }, [onCountdownComplete]);

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
          sessionStartedAtRef.current = null;
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

  const publicState = useMemo<TimerState>(() => {
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

      if (!sessionStartedAtRef.current) {
        sessionStartedAtRef.current = new Date().toISOString();
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
    setInternal({
      status: "paused",
      accumulatedMs: elapsedMs,
      runningStartedAt: null,
    });
  }, []);

  const getElapsedSeconds = useCallback((): number => {
    return Math.floor(computeElapsedMs(internalRef.current) / 1000);
  }, []);

  const getSessionStartedAt = useCallback((): string | null => {
    return sessionStartedAtRef.current;
  }, []);

  const reset = useCallback(() => {
    sessionStartedAtRef.current = null;
    setInternal(INITIAL);
  }, []);

  const flushOnUnmount = useCallback(() => {
    return getElapsedSeconds();
  }, [getElapsedSeconds]);

  return {
    state: publicState,
    isActive,
    start,
    pause,
    reset,
    getElapsedSeconds,
    getSessionStartedAt,
    flushOnUnmount,
  };
}
