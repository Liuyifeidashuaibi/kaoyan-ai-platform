"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowLeft, Loader2 } from "lucide-react";

import { StatsSection } from "@/app/(main)/timer/_components/stats-section";
import { useTimerData } from "@/app/(main)/timer/_hooks/use-timer-data";
import type { StatsPeriod } from "@/app/(main)/timer/_lib/types";
import { computeStatsSummary } from "@/app/(main)/timer/_lib/utils";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export function TomatoStatsPage() {
  const { status, subjects, sessions, preferences, error, loadData } =
    useTimerData();
  const [statsPeriod, setStatsPeriod] = useState<StatsPeriod>("today");

  const statsSummary = useMemo(
    () =>
      computeStatsSummary(
        subjects,
        sessions,
        statsPeriod,
        preferences.dailyGoalMinutes
      ),
    [subjects, sessions, statsPeriod, preferences.dailyGoalMinutes]
  );

  if (status === "loading") {
    return (
      <div className="flex items-center justify-center gap-2 p-12 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        番茄钟统计加载中…
      </div>
    );
  }

  if (status === "unconfigured") {
    return (
      <Alert variant="destructive" className="max-w-2xl">
        <AlertDescription>
          Supabase 未配置，无法加载番茄钟统计数据。
        </AlertDescription>
      </Alert>
    );
  }

  if (status === "unauthenticated") {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4">
        <Alert>
          <AlertDescription>请先登录后查看番茄钟统计。</AlertDescription>
        </Alert>
        <Link href="/login?next=/timer/stats">
          <Button type="button">前往登录</Button>
        </Link>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4">
        <Alert variant="destructive">
          <AlertDescription>{error ?? "番茄钟统计加载失败"}</AlertDescription>
        </Alert>
        <Button type="button" variant="outline" onClick={() => void loadData()}>
          重新加载
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div>
        <Link href="/timer">
          <Button type="button" variant="ghost" size="sm" className="-ml-2 mb-2">
            <ArrowLeft className="size-4" />
            返回番茄钟
          </Button>
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">番茄钟统计</h1>
        <p className="text-muted-foreground">学习数据可视化</p>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <StatsSection
        summary={statsSummary}
        period={statsPeriod}
        onPeriodChange={setStatsPeriod}
      />
    </div>
  );
}
