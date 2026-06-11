"use client";

import { memo } from "react";

import type { BarChartProps } from "@/components/TomatoClock/types";
import { formatHourMinute } from "@/components/TomatoClock/utils";

export const BarChart = memo(function BarChart({ items }: BarChartProps) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">暂无番茄钟统计数据</p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <ul className="min-w-[280px] space-y-4">
        {items.map((item) => (
          <li key={item.subjectId} className="space-y-1.5">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="truncate font-medium">{item.name}</span>
              <span
                className="shrink-0 tabular-nums text-muted-foreground"
                title={`精确时长：${formatHourMinute(item.durationSeconds)}`}
              >
                {item.formattedDuration}
              </span>
            </div>
            <div
              className="group relative h-3 w-full overflow-hidden rounded-full bg-muted"
              title={`${item.name}：${formatHourMinute(item.durationSeconds)}`}
            >
              <div
                className="h-full rounded-full transition-[width] duration-500 ease-out"
                style={{
                  width: `${item.barPercent}%`,
                  backgroundColor: item.color,
                }}
              />
              <span className="pointer-events-none absolute inset-y-0 right-2 hidden items-center text-[10px] text-white group-hover:flex">
                {formatHourMinute(item.durationSeconds)}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
});
