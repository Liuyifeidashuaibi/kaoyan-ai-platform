"use client";

import { Minus, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { TimerRing } from "./timer-ring";
import type { TimerMode, TimerSubject } from "./types";
import { cn } from "@/lib/utils";

interface TimerControlsProps {
  mode: TimerMode;
  onModeChange: (mode: TimerMode) => void;
  countdownMinutes: number;
  onCountdownMinutesChange: (minutes: number) => void;
  subjects: TimerSubject[];
  selectedSubject: TimerSubject | null;
  displayTime: string;
  progress: number;
  status: "idle" | "running" | "paused";
  isActive: boolean;
  saving?: boolean;
  onStart: () => void;
  onPause: () => void;
  onEnd: () => void;
}

export function TimerControls({
  mode,
  onModeChange,
  countdownMinutes,
  onCountdownMinutesChange,
  subjects,
  selectedSubject,
  displayTime,
  progress,
  status,
  isActive,
  saving,
  onStart,
  onPause,
  onEnd,
}: TimerControlsProps) {
  const controlsLocked = isActive;
  const ringColor = selectedSubject?.color ?? "#93C5FD";
  const ringProgress =
    mode === "countdown" ? (isActive ? progress : 1) : isActive ? progress : 0;

  function adjustMinutes(delta: number) {
    onCountdownMinutesChange(
      Math.min(180, Math.max(1, countdownMinutes + delta))
    );
  }

  return (
    <section className="rounded-3xl bg-white p-5 shadow-[0_4px_24px_rgba(0,0,0,0.06)] ring-1 ring-black/[0.03] sm:p-6">
      <div className="flex justify-center">
        <div className="inline-flex rounded-2xl bg-neutral-100/80 p-1">
          {(
            [
              { value: "countdown" as const, label: "Countdown" },
              { value: "stopwatch" as const, label: "Stopwatch" },
            ] as const
          ).map((item) => (
            <button
              key={item.value}
              type="button"
              disabled={controlsLocked}
              onClick={() => onModeChange(item.value)}
              className={cn(
                "rounded-xl px-5 py-2 text-sm font-medium transition-colors",
                mode === item.value
                  ? "bg-white text-neutral-900 shadow-sm"
                  : "text-neutral-500 hover:text-neutral-700",
                controlsLocked && "pointer-events-none opacity-50"
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 sm:mt-6">
        <TimerRing progress={ringProgress} color={ringColor}>
          <p className="text-4xl font-light tabular-nums tracking-tight text-neutral-900 sm:text-5xl">
            {displayTime}
          </p>
          {selectedSubject && (
            <p className="mt-2 text-sm font-medium text-neutral-500">
              {selectedSubject.name}
            </p>
          )}
        </TimerRing>
      </div>

      {mode === "countdown" && !isActive && (
        <div className="mt-5 flex flex-col items-center gap-2 sm:mt-6 sm:gap-3">
          <span className="text-sm font-medium text-neutral-500">
            Set Minutes
          </span>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => adjustMinutes(-5)}
              className="flex size-10 items-center justify-center rounded-xl bg-neutral-100 text-neutral-600 transition-colors hover:bg-neutral-200"
              aria-label="Decrease minutes"
            >
              <Minus className="size-4" />
            </button>
            <span className="min-w-[3rem] text-center text-2xl font-light tabular-nums text-neutral-900">
              {countdownMinutes}
            </span>
            <button
              type="button"
              onClick={() => adjustMinutes(5)}
              className="flex size-10 items-center justify-center rounded-xl bg-neutral-100 text-neutral-600 transition-colors hover:bg-neutral-200"
              aria-label="Increase minutes"
            >
              <Plus className="size-4" />
            </button>
          </div>
        </div>
      )}

      <div className="mt-6 flex justify-center gap-3 sm:mt-8">
        {status === "idle" && (
          <Button
            type="button"
            size="lg"
            disabled={!selectedSubject || saving}
            onClick={onStart}
            className="min-w-[180px] rounded-2xl bg-[#3B82F6] py-5 text-base font-medium text-white shadow-sm hover:bg-[#2563EB] sm:min-w-[200px] sm:py-6"
          >
            Start
          </Button>
        )}

        {status === "running" && (
          <>
            <Button
              type="button"
              size="lg"
              onClick={onPause}
              className="min-w-28 rounded-2xl bg-[#FBBF24] py-5 text-base font-medium text-white shadow-sm hover:bg-[#F59E0B] sm:py-6"
            >
              Pause
            </Button>
            <Button
              type="button"
              size="lg"
              disabled={saving}
              onClick={onEnd}
              className="min-w-28 rounded-2xl bg-[#EF4444] py-5 text-base font-medium text-white shadow-sm hover:bg-[#DC2626] sm:py-6"
            >
              End
            </Button>
          </>
        )}

        {status === "paused" && (
          <>
            <Button
              type="button"
              size="lg"
              onClick={onStart}
              className="min-w-28 rounded-2xl bg-[#22C55E] py-5 text-base font-medium text-white shadow-sm hover:bg-[#16A34A] sm:py-6"
            >
              Continue
            </Button>
            <Button
              type="button"
              size="lg"
              disabled={saving}
              onClick={onEnd}
              className="min-w-28 rounded-2xl bg-[#EF4444] py-5 text-base font-medium text-white shadow-sm hover:bg-[#DC2626] sm:py-6"
            >
              End
            </Button>
          </>
        )}
      </div>

      {subjects.length === 0 && (
        <p className="mt-6 text-center text-sm text-neutral-400">
          Add a subject before starting the timer.
        </p>
      )}
    </section>
  );
}
