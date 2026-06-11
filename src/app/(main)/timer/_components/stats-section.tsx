"use client";

import { memo } from "react";

import { BarChart } from "@/app/(main)/timer/_components/bar-chart";
import { CircleProgress } from "@/app/(main)/timer/_components/circle-progress";
import type { StatsPeriod, TimerStatsSummary } from "@/app/(main)/timer/_lib/types";
import { formatHourMinute, getPeriodLabel } from "@/app/(main)/timer/_lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface StatsSectionProps {
  summary: TimerStatsSummary;
  period: StatsPeriod;
  onPeriodChange: (period: StatsPeriod) => void;
}

export const StatsSection = memo(function StatsSection({
  summary,
  period,
  onPeriodChange,
}: StatsSectionProps) {
  const periodLabel = getPeriodLabel(period);

  return (
    <Card>
      <CardHeader>
        <CardTitle>番茄钟统计</CardTitle>
        <CardDescription>
          上半区为整体学习进度，下半区为各科目累计时长
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <Tabs
          value={period}
          onValueChange={(value) => onPeriodChange(value as StatsPeriod)}
        >
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="today">今日</TabsTrigger>
            <TabsTrigger value="week">本周</TabsTrigger>
            <TabsTrigger value="month">本月</TabsTrigger>
            <TabsTrigger value="all">总计</TabsTrigger>
          </TabsList>

          <TabsContent value={period} className="mt-6 space-y-8">
            <div className="flex flex-col items-center gap-4 border-b border-border pb-8">
              <CircleProgress
                percent={summary.goalPercent}
                subtitle={`${periodLabel}番茄钟进度`}
              />
              <p className="text-center text-sm text-muted-foreground">
                {periodLabel}学习 {summary.formattedTotal} / 目标{" "}
                {formatHourMinute(summary.goalSeconds)}
              </p>
            </div>

            <div>
              <h3 className="mb-2 text-sm font-medium">
                {periodLabel}总学习时长
              </h3>
              <p className="mb-4 text-2xl font-semibold tabular-nums">
                {summary.formattedTotal}
              </p>
              <h3 className="mb-4 text-sm font-medium">
                {periodLabel}各科目学习时长
              </h3>
              {summary.barItems.every((item) => item.durationSeconds === 0) ? (
                <p className="text-sm text-muted-foreground">暂无番茄钟记录</p>
              ) : (
                <BarChart items={summary.barItems} />
              )}
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
});
