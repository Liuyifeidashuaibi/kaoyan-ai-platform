"use client";

import { useEffect, useState } from "react";

import { AdminModulePage } from "@/components/admin/layout/admin-module-page";
import { PageSection } from "@/components/admin/shared/page-section";
import { StatusDot } from "@/components/admin/shared/status-dot";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { adminNavItems } from "@/config/admin-navigation";
import { fetchMonitoringSection } from "@/lib/admin/api/monitoring";
import { ApiError } from "@/lib/api/client";
import { formatAdminDate } from "@/components/admin/data-table/admin-data-table";

const nav = adminNavItems.find((item) => item.id === "monitoring")!;

const titles: Record<string, string> = {
  api: "API 状态",
  database: "数据库状态",
  agents: "Agent 状态",
  errors: "错误日志",
  queue: "任务队列",
};

function StatCard({
  label,
  value,
  detail,
  status = "idle",
}: {
  label: string;
  value: string;
  detail?: string;
  status?: "idle" | "running" | "warning" | "error";
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-card p-5">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <StatusDot variant={status === "running" ? "running" : status === "warning" ? "warning" : status === "error" ? "error" : "idle"} />
      </div>
      <p className="mt-3 text-2xl font-medium">{value}</p>
      {detail ? <p className="mt-1 text-xs text-muted-foreground">{detail}</p> : null}
    </div>
  );
}

export function MonitoringSectionClient({ section }: { section: string }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchMonitoringSection(section)
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [section]);

  return (
    <AdminModulePage title={titles[section] ?? section} subNav={nav.children}>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
        </div>
      ) : data ? (
        <div className="space-y-6">
          {section === "api" ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <StatCard
                label="API 状态"
                value={String(data.status ?? "unknown")}
                detail={`延迟 ${data.latencyMs ?? "—"}ms`}
                status={data.status === "ok" ? "running" : "warning"}
              />
              <StatCard
                label="LLM 配置"
                value={data.llmConfigured ? "已配置" : "未配置"}
                status={data.llmConfigured ? "running" : "warning"}
              />
            </div>
          ) : null}

          {section === "database" ? (
            <>
              <StatCard
                label="数据库连接"
                value={data.connected ? "已连接" : "异常"}
                detail={String(data.status ?? "")}
                status={data.connected ? "running" : "error"}
              />
              <PageSection title="表记录数">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {Object.entries((data.tables as Record<string, unknown>) ?? {}).map(
                    ([table, count]) => (
                      <div
                        key={table}
                        className="flex items-center justify-between rounded-lg border border-border/60 px-4 py-3 text-sm"
                      >
                        <span className="text-muted-foreground">{table}</span>
                        <span className="font-medium tabular-nums">{String(count)}</span>
                      </div>
                    )
                  )}
                </div>
              </PageSection>
            </>
          ) : null}

          {section === "agents" && Array.isArray(data.agents) ? (
            <div className="grid gap-3 sm:grid-cols-3">
              {(data.agents as { name: string; status: string; successRate: string; taskCount: number }[]).map(
                (agent) => (
                  <div key={agent.name} className="rounded-xl border border-border/60 bg-card p-4">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{agent.name}</span>
                      <Badge variant="outline">{agent.status}</Badge>
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">
                      成功率 {agent.successRate} · 任务 {agent.taskCount}
                    </p>
                  </div>
                )
              )}
            </div>
          ) : null}

          {section === "queue" ? (
            <>
              <StatCard
                label="待处理"
                value={String(data.pending ?? 0)}
                status={(data.pending as number) > 0 ? "running" : "idle"}
              />
              {Array.isArray(data.tasks) && data.tasks.length > 0 ? (
                <PageSection title="最近任务">
                  <div className="space-y-2">
                    {(data.tasks as { id: string; title: string; status: string; progress: number }[]).map(
                      (task) => (
                        <div
                          key={task.id}
                          className="rounded-lg border border-border/60 bg-card p-3"
                        >
                          <div className="flex items-center justify-between gap-2 text-sm">
                            <span className="truncate font-medium">{task.title}</span>
                            <Badge variant="outline">{task.status}</Badge>
                          </div>
                          <div className="mt-2">
                            <Progress value={task.progress ?? 0} />
                          </div>
                        </div>
                      )
                    )}
                  </div>
                </PageSection>
              ) : null}
            </>
          ) : null}

          {section === "errors" ? (
            <>
              {Array.isArray(data.items) && data.items.length > 0 ? (
                <PageSection title="系统错误">
                  <ul className="divide-y divide-border/60 rounded-xl border border-border/60 bg-card">
                    {(data.items as { id: string; source: string; message: string; time: string }[]).map(
                      (item) => (
                        <li key={item.id} className="px-4 py-3 text-sm">
                          <div className="flex justify-between gap-4">
                            <span className="font-medium">{item.source}</span>
                            <span className="text-xs text-muted-foreground">
                              {formatAdminDate(item.time)}
                            </span>
                          </div>
                          <p className="mt-1 text-muted-foreground">{item.message}</p>
                        </li>
                      )
                    )}
                  </ul>
                </PageSection>
              ) : (
                <p className="text-sm text-muted-foreground">暂无错误记录</p>
              )}
              {Array.isArray(data.auditLogs) && data.auditLogs.length > 0 ? (
                <PageSection title="管理操作审计">
                  <ul className="divide-y divide-border/60 rounded-xl border border-border/60 bg-card">
                    {(
                      data.auditLogs as {
                        time: string;
                        actor: string;
                        action: string;
                        resource: string;
                      }[]
                    ).map((entry, i) => (
                      <li key={`${entry.time}-${i}`} className="px-4 py-3 text-sm">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-medium">{entry.action}</span>
                          <span className="text-xs text-muted-foreground">
                            {formatAdminDate(entry.time)}
                          </span>
                        </div>
                        <p className="mt-1 text-muted-foreground">
                          {entry.actor}
                          {entry.resource ? ` · ${entry.resource}` : ""}
                        </p>
                      </li>
                    ))}
                  </ul>
                </PageSection>
              ) : null}
            </>
          ) : null}
        </div>
      ) : null}
    </AdminModulePage>
  );
}
