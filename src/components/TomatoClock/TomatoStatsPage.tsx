"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { StatsSection } from "@/components/TomatoClock/StatsSection";
import { getTomatoStorage } from "@/components/TomatoClock/storage";
import type { StatsPeriod, TomatoStorage } from "@/components/TomatoClock/types";
import { computeStatsSummary } from "@/components/TomatoClock/utils";
import { Button } from "@/components/ui/button";
import { useMemo, useState } from "react";

export function TomatoStatsPage() {
  const [storage] = useState<TomatoStorage>(() => getTomatoStorage());
  const [statsPeriod, setStatsPeriod] = useState<StatsPeriod>("today");

  const statsSummary = useMemo(
    () => computeStatsSummary(storage, statsPeriod),
    [storage, statsPeriod]
  );

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-4 sm:p-0">
      <div>
        <Link href="/study/tomato">
          <Button type="button" variant="ghost" size="sm" className="-ml-2 mb-2">
            <ArrowLeft className="size-4" />
            返回番茄钟
          </Button>
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">番茄钟统计</h1>
        <p className="text-muted-foreground">本地学习数据可视化</p>
      </div>

      <StatsSection
        summary={statsSummary}
        period={statsPeriod}
        onPeriodChange={setStatsPeriod}
      />
    </div>
  );
}
