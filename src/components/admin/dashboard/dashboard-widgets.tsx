import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { StatusDot, type StatusDotVariant } from "@/components/admin/shared/status-dot";
import { cn } from "@/lib/utils";

export type AgentSummary = {
  id: string;
  name: string;
  status: StatusDotVariant;
  lastRun: string;
  successRate: string;
  taskCount: number;
  pulse?: boolean;
};

export function AgentStatusTile({ agent }: { agent: AgentSummary }) {
  const statusLabel =
    agent.status === "running"
      ? "运行中"
      : agent.status === "warning"
        ? "告警"
        : agent.status === "error"
          ? "异常"
          : "空闲";

  return (
    <Link
      href="/admin/agents"
      className="group flex flex-col gap-3 rounded-xl border border-border/60 bg-card p-4 transition-colors hover:border-border"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{agent.name}</span>
        <StatusDot variant={agent.status} pulse={agent.pulse} />
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{statusLabel}</span>
        <span>{agent.lastRun}</span>
      </div>
      <div className="flex items-center justify-between border-t border-border/40 pt-3 text-xs">
        <span className="text-muted-foreground">成功率 {agent.successRate}</span>
        <span className="tabular-nums text-foreground">今日 {agent.taskCount}</span>
      </div>
    </Link>
  );
}

export function DashboardAgentSummary({ agents }: { agents: AgentSummary[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {agents.map((agent) => (
        <AgentStatusTile key={agent.id} agent={agent} />
      ))}
    </div>
  );
}

export type ActivityItem = {
  id: string;
  type: "user" | "post" | "agent" | "sync" | "report";
  message: string;
  time: string;
  href?: string;
};

const activityTypeLabel: Record<ActivityItem["type"], string> = {
  user: "用户",
  post: "社区",
  agent: "Agent",
  sync: "同步",
  report: "举报",
};

export function ActivityFeed({ items }: { items: ActivityItem[] }) {
  return (
    <ul className="divide-y divide-border/60">
      {items.map((item) => (
        <li key={item.id} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
          <Badge variant="outline" className="mt-0.5 shrink-0 font-normal">
            {activityTypeLabel[item.type]}
          </Badge>
          <div className="min-w-0 flex-1 space-y-1">
            <p className="text-sm text-foreground">{item.message}</p>
            <p className="text-xs text-muted-foreground">{item.time}</p>
          </div>
          {item.href ? (
            <Link
              href={item.href}
              className="shrink-0 text-muted-foreground transition-colors hover:text-foreground"
              aria-label="查看详情"
            >
              <ArrowRight className="size-4" />
            </Link>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export function DashboardMetrics({
  metrics,
  className,
}: {
  metrics: {
    label: string;
    value: string | number;
    delta?: string;
    deltaTrend?: "up" | "down" | "neutral";
  }[];
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6",
        className
      )}
    >
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className="flex flex-col gap-3 rounded-xl border border-border/60 bg-card px-4 py-4"
        >
          <span className="text-sm text-muted-foreground">{metric.label}</span>
          <span className="text-2xl font-medium tracking-tight tabular-nums xl:text-3xl">
            {metric.value}
          </span>
          {metric.delta ? (
            <span
              className={cn(
                "text-xs",
                metric.deltaTrend === "up"
                  ? "text-emerald-600"
                  : metric.deltaTrend === "down"
                    ? "text-red-600"
                    : "text-muted-foreground"
              )}
            >
              {metric.delta}
            </span>
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          )}
        </div>
      ))}
    </div>
  );
}
