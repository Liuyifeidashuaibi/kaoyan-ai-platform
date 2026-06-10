"use client";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { StatsDashboard } from "@/components/study-timer/stats-dashboard";
import { useStudySubjects } from "@/hooks/study-timer/use-study-subjects";
import { formatDurationZh } from "@/lib/study-timer/utils";

export function StudyStatsPage() {
  const { stats, totalSeconds, loading, error, notice } = useStudySubjects();

  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">统计看板</h1>
          <p className="text-muted-foreground">
            汇总所有科目的累计学习时长，总时长 {formatDurationZh(totalSeconds)}
          </p>
        </div>
        <a
          href="/pomodoro"
          className="text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          ← 返回科目列表
        </a>
      </div>

      {notice ? (
        <Alert>
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      ) : null}

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <StatsDashboard stats={stats} loading={loading} totalSeconds={totalSeconds} />
    </div>
  );
}
