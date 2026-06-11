"use client";

import { formatHourMinute } from "@/app/(main)/timer/_lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface DailySummaryProps {
  todaySeconds: number;
}

export function DailySummary({ todaySeconds }: DailySummaryProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">今日番茄钟</CardTitle>
        <CardDescription>每日计时数据统计</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-bold tabular-nums text-primary">
          {formatHourMinute(todaySeconds)}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          今日累计学习时长
        </p>
      </CardContent>
    </Card>
  );
}
