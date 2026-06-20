"use client";

import { useCallback, useEffect, useState } from "react";

import { AdminModulePage } from "@/components/admin/layout/admin-module-page";
import { PageSection } from "@/components/admin/shared/page-section";
import { StatusDot } from "@/components/admin/shared/status-dot";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { adminNavItems } from "@/config/admin-navigation";
import { fetchMonitoringHealth, type MonitoringHealth } from "@/lib/admin/api/monitoring";
import { ApiError } from "@/lib/api/client";

const nav = adminNavItems.find((item) => item.id === "monitoring")!;

function StatusCard({
  title,
  status,
  detail,
}: {
  title: string;
  status: "ok" | "degraded" | "error" | "idle" | "running";
  detail: string;
}) {
  const dot =
    status === "ok" || status === "running"
      ? "running"
      : status === "degraded"
        ? "warning"
        : status === "error"
          ? "error"
          : "idle";

  return (
    <div className="rounded-xl border border-border/60 bg-card p-5">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{title}</span>
        <StatusDot variant={dot} pulse={status === "running"} />
      </div>
      <p className="mt-3 text-2xl font-medium capitalize tabular-nums">{status}</p>
      <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
    </div>
  );
}

export function MonitoringOverviewClient() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<MonitoringHealth | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchMonitoringHealth();
      setHealth(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <AdminModulePage
      title="系统监控"
      description="API、数据库、Agent 与任务队列健康状态"
      subNav={nav.children}
    >
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
      ) : health ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatusCard
              title="API"
              status={health.api.status === "ok" ? "ok" : "degraded"}
              detail={`延迟 ${health.api.latencyMs}ms`}
            />
            <StatusCard
              title="数据库"
              status={health.database.connected ? "ok" : "degraded"}
              detail={health.database.connected ? "Supabase 已连接" : "连接异常"}
            />
            <StatusCard
              title="Agent"
              status={health.agent.status === "running" ? "running" : "idle"}
              detail={`活跃任务 ${health.agent.activeTasks}`}
            />
            <StatusCard
              title="任务队列"
              status={health.queue.pending > 0 ? "running" : "idle"}
              detail={`待处理 ${health.queue.pending}`}
            />
          </div>

          <PageSection title="服务配置">
            <div className="flex flex-wrap gap-2">
              <Badge variant={health.llmConfigured ? "secondary" : "destructive"}>
                LLM {health.llmConfigured ? "已配置" : "未配置"}
              </Badge>
            </div>
          </PageSection>
        </div>
      ) : null}
    </AdminModulePage>
  );
}
