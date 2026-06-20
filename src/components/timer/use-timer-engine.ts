"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { TimerMode, TimerRunStatus } from "./types";
import { formatMmSs } from "./utils";

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
}

export function useTimerEngine({ mode, countdownSeconds }: UseTimerEngineOptions) {
  const [internal, setInternal] = useState<TimerInternalState>(INITIAL);
  const [tick, setTick] = useState(0);
  const sessionStartedAtRef = useRef<string | null>(null);
  const internalRef = useRef(internal);

  useEffect(() => {
    internalRef.current = internal;
  }, [internal]);

  useEffect(() => {
    if (internal.status !== "running") return;

    let frameId = 0;

    const loop = () => {
      const snapshot = internalRef.current;
      const elapsedMs = computeElapsedMs(snapshot);

      if (mode === "countdown") {
        const remainingMs = countdownSeconds * 1000 - elapsedMs;
        if (remainingMs <= 0) {
          setInternal({
            status: "paused",
            accumulatedMs: countdownSeconds * 1000,
            runningStartedAt: null,
          });
          setTick((value) => value + 1);
          return;
        }
      }

      setTick((value) => value + 1);
      frameId = window.requestAnimationFrame(loop);
    };

    frameId = window.requestAnimationFrame(loop);
    return () => window.cancelAnimationFrame(frameId);
  }, [countdownSeconds, internal.status, mode]);

  const displayTime = useMemo(() => {
    const elapsedMs = computeElapsedMs(internal);
    const elapsedSeconds = Math.floor(elapsedMs / 1000);

    if (mode === "stopwatch") {
      return formatMmSs(elapsedSeconds);
    }

    const remainingSeconds = Math.max(
      0,
      Math.ceil((countdownSeconds * 1000 - elapsedMs) / 1000)
    );
    return formatMmSs(remainingSeconds);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- tick drives live updates
  }, [countdownSeconds, internal, mode, tick]);

  const status = internal.status;
  const isActive = status !== "idle";

  const start = useCallback(() => {
    setInternal((prev) => {
      if (prev.status === "running") return prev;

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

  const clearSession = useCallback(() => {
    sessionStartedAtRef.current = null;
    setInternal(INITIAL);
  }, []);

  const progress = useMemo(() => {
    const elapsedMs = computeElapsedMs(internal);
    if (mode === "countdown") {
      if (countdownSeconds <= 0) return 0;
      return Math.max(
        0,
        (countdownSeconds * 1000 - elapsedMs) / (countdownSeconds * 1000)
      );
    }
    return Math.min(1, elapsedMs / (3600 * 1000));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- tick drives live updates
  }, [countdownSeconds, internal, mode, tick]);

  return {
    displayTime,
    status,
    isActive,
    progress,
    start,
    pause,
    getElapsedSeconds,
    getSessionStartedAt,
    clearSession,
  };
}
