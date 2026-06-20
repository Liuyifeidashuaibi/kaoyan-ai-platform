import type { Metadata } from "next";
import Link from "next/link";

import { DashboardDataBanner } from "@/components/admin/dashboard/dashboard-data-banner";
import { DashboardExportButton } from "@/components/admin/dashboard/dashboard-export-button";
import { AdminPage } from "@/components/admin/layout/admin-shell";
import {
  ActivityFeed,
  DashboardAgentSummary,
  DashboardMetrics,
} from "@/components/admin/dashboard/dashboard-widgets";
import { AdminPageHeader } from "@/components/admin/layout/admin-page-header";
import { PageSection } from "@/components/admin/shared/page-section";
import { Button } from "@/components/ui/button";
import { adminServerFetchResult } from "@/lib/admin/api/server";
import {
  dashboardActivity as mockActivity,
  dashboardAgents as mockAgents,
  dashboardMetrics as mockMetrics,
} from "@/lib/admin/mock/dashboard";

export const metadata: Metadata = {
  title: "Dashboard",
};

type MetricsData = {
  usersTotal: number;
  postsTotal: number;
  schoolsTotal: number;
  majorsTotal: number;
  usersToday: number;
  postsToday: number;
  degraded?: boolean;
  degradedReason?: string;
};

function toMetricCards(data: MetricsData) {
  return [
    { label: "总用户数", value: data.usersTotal.toLocaleString(), delta: "—", deltaTrend: "neutral" as const },
    { label: "总帖子数", value: data.postsTotal.toLocaleString(), delta: "—", deltaTrend: "neutral" as const },
    { label: "学校数量", value: data.schoolsTotal.toLocaleString(), delta: "—", deltaTrend: "neutral" as const },
    { label: "专业数量", value: data.majorsTotal.toLocaleString(), delta: "—", deltaTrend: "neutral" as const },
    { label: "今日新增用户", value: data.usersToday.toLocaleString(), delta: "今日", deltaTrend: "up" as const },
    { label: "今日新增帖子", value: data.postsToday.toLocaleString(), delta: "今日", deltaTrend: "up" as const },
  ];
}

export default async function AdminDashboardPage() {
  const now = new Date();
  const timeLabel = now.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });

  const [metricsResult, activityResult, agentsResult] = await Promise.all([
    adminServerFetchResult<MetricsData>("/api/admin/dashboard/metrics"),
    adminServerFetchResult<
      { id: string; type: "user" | "post" | "agent" | "sync" | "report"; message: string; time: string; href?: string }[]
    >("/api/admin/dashboard/activity?limit=8"),
    adminServerFetchResult<
      { id: string; name: string; status: string; lastRun: string; successRate: string; taskCount: number }[]
    >("/api/admin/agents/status"),
  ]);

  const metricsData = metricsResult.ok ? metricsResult.data : null;
  const activityData = activityResult.ok ? activityResult.data : null;
  const agentsData = agentsResult.ok ? agentsResult.data : null;

  const apiErrors: string[] = [];
  if (!metricsResult.ok) apiErrors.push(`指标（${metricsResult.error}）`);
  else if (metricsData?.degraded) {
    apiErrors.push(metricsData.degradedReason || "指标为演示数据（未连接 Supabase）");
  }
  if (!activityResult.ok) apiErrors.push(`活动（${activityResult.error}）`);
  if (!agentsResult.ok) apiErrors.push(`Agent（${agentsResult.error}）`);

  const metrics = metricsData
    ? toMetricCards(metricsData)
    : mockMetrics;

  const activity = activityData?.length
    ? activityData.map((item) => ({
        ...item,
        time: formatRelativeTime(item.time),
      }))
    : mockActivity;

  const agents = agentsData?.length
    ? agentsData.map((a) => ({
        id: a.id,
        name: a.name,
        status: mapAgentStatus(a.status),
        lastRun: a.lastRun,
        successRate: a.successRate,
        taskCount: a.taskCount,
        pulse: a.status === "running",
      }))
    : mockAgents;

  return (
    <AdminPage>
      <div className="space-y-8">
        <AdminPageHeader
          title="运营总览"
          description={`今日数据截至 ${timeLabel} · 核心指标与系统动态`}
          actions={<DashboardExportButton />}
        />

        <DashboardDataBanner errors={apiErrors} />

        <DashboardMetrics metrics={metrics} />

        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <PageSection
            title="Agent 运行状态"
            description="各 Agent 最近执行与成功率摘要"
            action={
              <Button variant="ghost" size="sm" asChild>
                <Link href="/admin/agents">进入控制中心</Link>
              </Button>
            }
          >
            <DashboardAgentSummary agents={agents} />
          </PageSection>

          <PageSection title="最近系统活动" description="平台关键事件时间线">
            <div className="rounded-xl border border-border/60 bg-card p-4">
              <ActivityFeed items={activity} />
            </div>
          </PageSection>
        </div>
      </div>
    </AdminPage>
  );
}

function mapAgentStatus(status: string): "idle" | "running" | "warning" | "error" {
  if (status === "running") return "running";
  if (status === "warning") return "warning";
  if (status === "error") return "error";
  return "idle";
}

function formatRelativeTime(iso: string) {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "刚刚";
    if (mins < 60) return `${mins} 分钟前`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours} 小时前`;
    return new Date(iso).toLocaleDateString("zh-CN");
  } catch {
    return iso;
  }
}
