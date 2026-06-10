import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatDurationZh } from "@/lib/study-timer/utils";
import type { SubjectStatItem } from "@/types/study-timer";

interface StatsDashboardProps {
  stats: SubjectStatItem[];
  totalSeconds: number;
  loading: boolean;
}

export function StatsDashboard({
  stats,
  totalSeconds,
  loading,
}: StatsDashboardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>科目时长汇总</CardTitle>
        <CardDescription>
          总计 {formatDurationZh(totalSeconds)}，各科目以专属颜色区分
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-sm text-muted-foreground">加载中…</p>
        ) : stats.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            暂无统计数据，完成一次计时会自动记录。
          </p>
        ) : (
          <ul className="space-y-4">
            {stats.map((item) => (
              <li key={item.subject.id} className="space-y-2">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <span
                      className="size-3 rounded-full"
                      style={{ backgroundColor: item.subject.color }}
                      aria-hidden
                    />
                    <span className="font-medium">{item.subject.name}</span>
                  </div>
                  <span className="text-sm text-muted-foreground">
                    {item.formattedDuration} · {item.percentage}%
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${Math.min(item.percentage, 100)}%`,
                      backgroundColor: item.subject.color,
                    }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
