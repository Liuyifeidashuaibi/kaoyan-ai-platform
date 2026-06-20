"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowLeft } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { DoughnutChart } from "./doughnut-chart";
import { StatsToday } from "./stats-today";
import { TimerGate } from "./timer-gate";
import type { StatsTab } from "./types";
import { useTimerData } from "./use-timer-data";
import { buildSubjectStats, formatDurationEn } from "./utils";
import { cn } from "@/lib/utils";

const TABS: { value: StatsTab; label: string }[] = [
  { value: "today", label: "Today" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "total", label: "Total" },
];

const PERIOD_LABEL: Record<Exclude<StatsTab, "today">, string> = {
  week: "This Week",
  month: "This Month",
  total: "All Time",
};

export function StatisticsPage() {
  const { status, subjects, sessions, error, loadData } = useTimerData();
  const [tab, setTab] = useState<StatsTab>("today");

  const todayItems = useMemo(
    () => buildSubjectStats(subjects, sessions, "today", false),
    [sessions, subjects]
  );

  const weekItems = useMemo(
    () => buildSubjectStats(subjects, sessions, "week", true),
    [sessions, subjects]
  );

  const monthItems = useMemo(
    () => buildSubjectStats(subjects, sessions, "month", true),
    [sessions, subjects]
  );

  const totalItems = useMemo(
    () => buildSubjectStats(subjects, sessions, "all", true),
    [sessions, subjects]
  );

  function totalSeconds(items: typeof todayItems) {
    return items.reduce((sum, item) => sum + item.durationSeconds, 0);
  }

  return (
    <TimerGate
      status={status}
      error={error}
      title="Statistics"
      loginNext="/study/tomato/statistics"
      onRetry={() => void loadData()}
    >
      <div className="mx-auto max-w-2xl space-y-6 px-4 py-8 sm:px-6">
        <header className="flex items-center gap-4">
          <Link
            href="/study/tomato"
            className={cn(
              buttonVariants({ variant: "ghost", size: "icon-sm" }),
              "shrink-0 rounded-xl"
            )}
            aria-label="Back to Timer"
          >
            <ArrowLeft className="size-4" />
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
            Statistics
          </h1>
        </header>

        <div className="rounded-3xl bg-white p-1.5 shadow-[0_4px_24px_rgba(0,0,0,0.06)] ring-1 ring-black/[0.03]">
          <div className="grid grid-cols-4 gap-1">
            {TABS.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setTab(item.value)}
                className={cn(
                  "rounded-2xl py-2.5 text-sm font-medium transition-colors",
                  tab === item.value
                    ? "bg-neutral-900 text-white shadow-sm"
                    : "text-neutral-500 hover:text-neutral-700"
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <section className="rounded-3xl bg-white p-8 shadow-[0_4px_24px_rgba(0,0,0,0.06)] ring-1 ring-black/[0.03]">
          {tab === "today" && <StatsToday items={todayItems} />}

          {tab === "week" && (
            <DoughnutChart
              items={weekItems}
              centerTop="Total"
              centerMain={formatDurationEn(totalSeconds(weekItems))}
              centerBottom={PERIOD_LABEL.week}
            />
          )}

          {tab === "month" && (
            <DoughnutChart
              items={monthItems}
              centerTop="Total"
              centerMain={formatDurationEn(totalSeconds(monthItems))}
              centerBottom={PERIOD_LABEL.month}
            />
          )}

          {tab === "total" && (
            <div>
              <p className="mb-6 text-sm font-medium text-neutral-500">
                Total Study Distribution
              </p>
              <DoughnutChart
                items={totalItems}
                centerTop="Total"
                centerMain={formatDurationEn(totalSeconds(totalItems))}
                centerBottom={PERIOD_LABEL.total}
              />
            </div>
          )}
        </section>
      </div>
    </TimerGate>
  );
}
