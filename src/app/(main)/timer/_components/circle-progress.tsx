"use client";

import { memo } from "react";

import type { CircleProgressProps } from "@/app/(main)/timer/_lib/types";

function clampPercent(value: number): number {
  return Math.min(100, Math.max(0, Math.round(value)));
}

export const CircleProgress = memo(function CircleProgress({
  percent,
  subtitle = "今日番茄钟进度",
  size = 220,
}: CircleProgressProps) {
  const safePercent = clampPercent(percent);
  const strokeWidth = 12;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (safePercent / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          className="size-full -rotate-90"
          viewBox={`0 0 ${size} ${size}`}
          aria-hidden
        >
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            className="text-muted"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="text-primary transition-[stroke-dashoffset] duration-700 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold tabular-nums sm:text-4xl">
            {safePercent}%
          </span>
          <span className="text-xs text-muted-foreground sm:text-sm">
            {subtitle}
          </span>
        </div>
      </div>
    </div>
  );
});
