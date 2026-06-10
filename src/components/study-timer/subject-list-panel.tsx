import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatDurationZh } from "@/lib/study-timer/utils";
import type { StudySubject } from "@/types/study-timer";

interface SubjectListPanelProps {
  subjects: StudySubject[];
  loading: boolean;
}

export function SubjectListPanel({ subjects, loading }: SubjectListPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>我的科目</CardTitle>
        <CardDescription>点击科目进入独立计时页面</CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-sm text-muted-foreground">加载中…</p>
        ) : subjects.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            还没有科目，请先创建一个学习项目。
          </p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {subjects.map((subject) => (
              <li key={subject.id}>
                <Link
                  href={`/pomodoro/${subject.id}`}
                  className="flex items-center justify-between rounded-lg border border-border p-4 transition-colors hover:bg-muted/50"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className="size-3 shrink-0 rounded-full"
                      style={{ backgroundColor: subject.color }}
                      aria-hidden
                    />
                    <div>
                      <p className="font-medium">{subject.name}</p>
                      <p className="text-xs text-muted-foreground">
                        累计 {formatDurationZh(subject.totalSeconds)}
                      </p>
                    </div>
                  </div>
                  <Badge variant="secondary">开始计时</Badge>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
