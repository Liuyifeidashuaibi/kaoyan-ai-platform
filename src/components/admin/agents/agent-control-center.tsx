"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Send } from "lucide-react";

import { AdminPage } from "@/components/admin/layout/admin-shell";
import { AdminPageHeader } from "@/components/admin/layout/admin-page-header";
import { AgentStatusTile } from "@/components/admin/dashboard/dashboard-widgets";
import { RiskBadge } from "@/components/admin/shared/risk-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import {
  cancelAgentTask,
  createAgentPlan,
  executeAgentPlan,
  fetchAgentStatus,
  fetchAgentTasks,
  retryAgentTask,
  type AgentPlan,
  type AgentTask,
} from "@/lib/admin/api/agents";
import { agentQuickChips } from "@/lib/admin/mock/agents";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";

export function AgentControlCenter() {
  const [input, setInput] = useState("");
  const [plan, setPlan] = useState<AgentPlan | null>(null);
  const [confirmText, setConfirmText] = useState("");
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [agents, setAgents] = useState<
    {
      id: string;
      name: string;
      status: "idle" | "running" | "warning" | "error";
      lastRun: string;
      successRate: string;
      taskCount: number;
      pulse?: boolean;
    }[]
  >([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"all" | "running" | "failed">("all");

  const refresh = useCallback(async () => {
    try {
      const [statusRes, tasksRes] = await Promise.all([
        fetchAgentStatus(),
        fetchAgentTasks(),
      ]);
      if (statusRes) {
        setAgents(
          statusRes.map((a) => ({
            id: a.id,
            name: a.name,
            status:
              a.status === "running"
                ? "running"
                : a.status === "warning"
                  ? "warning"
                  : a.status === "error"
                    ? "error"
                    : "idle",
            lastRun: a.lastRun,
            successRate: a.successRate,
            taskCount: a.taskCount,
            pulse: a.status === "running",
          }))
        );
      }
      if (tasksRes) setTasks(tasksRes);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载失败");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const hasRunning = tasks.some((t) => t.status === "running");

  useEffect(() => {
    if (!hasRunning) return;
    const timer = window.setInterval(() => {
      void refresh();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [hasRunning, refresh]);

  async function handlePlan(intent: string) {
    if (!intent.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await createAgentPlan(intent.trim());
      if (res) setPlan(res);
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "生成计划失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleExecute() {
    if (!plan) return;
    if (plan.risk === "high" && confirmText !== "CONFIRM") {
      setError("高风险操作请输入 CONFIRM 确认");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await executeAgentPlan(plan.planId);
      setPlan(null);
      setConfirmText("");
      setInput("");
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "执行失败");
    } finally {
      setLoading(false);
    }
  }

  const filteredTasks = tasks.filter((t) => {
    if (tab === "running") return t.status === "running";
    if (tab === "failed") return t.status === "failed" || t.statusLabel === "已取消";
    return true;
  });

  return (
    <AdminPage className="flex max-w-none flex-col px-4 py-6 lg:px-6">
      <div className="mb-6">
        <AdminPageHeader
          title="Agent Control Center"
          description="状态监视 · 任务编排 · 自然语言助手（需确认后执行）"
          actions={
            <>
              <Button variant="outline" size="sm" onClick={() => void refresh()}>
                <RefreshCw className="size-3.5" />
                刷新
              </Button>
            </>
          }
        />
      </div>

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}

      <div className="flex min-h-0 flex-1 flex-col gap-4 lg:flex-row">
        <aside className="w-full shrink-0 space-y-4 lg:w-[260px]">
          <div className="rounded-xl border border-border/60 bg-card p-4">
            <p className="text-xs font-medium text-muted-foreground">全局摘要</p>
            <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-muted-foreground">任务数</p>
                <p className="font-medium tabular-nums">{tasks.length}</p>
              </div>
              <div>
                <p className="text-muted-foreground">运行中</p>
                <p className="font-medium tabular-nums">
                  {tasks.filter((t) => t.status === "running").length}
                </p>
              </div>
            </div>
          </div>
          <div className="space-y-2">
            {agents.map((agent) => (
              <AgentStatusTile key={agent.id} agent={agent} />
            ))}
          </div>
        </aside>

        <section className="min-w-0 flex-1 space-y-4">
          <div className="flex gap-1 border-b border-border/60">
            {(
              [
                ["all", "全部"],
                ["running", "执行中"],
                ["failed", "失败"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className={cn(
                  "px-3 py-2 text-sm transition-colors",
                  tab === key
                    ? "font-medium text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="space-y-3">
            {filteredTasks.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border/80 py-12 text-center text-sm text-muted-foreground">
                暂无任务，在下方输入自然语言指令创建计划
              </div>
            ) : (
              filteredTasks.map((task) => (
                <div
                  key={task.id}
                  className="rounded-xl border border-border/60 bg-card p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={
                            task.status === "failed"
                              ? "destructive"
                              : task.status === "running"
                                ? "secondary"
                                : "outline"
                          }
                        >
                          {task.statusLabel}
                        </Badge>
                        <span className="text-sm font-medium">{task.title}</span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Task #{task.id.slice(0, 8)} · {task.agent}
                      </p>
                    </div>
                  </div>
                  {task.progress > 0 && (task.status === "running" || task.status === "done") ? (
                    <div className="mt-3">
                      <Progress value={task.progress} />
                    </div>
                  ) : null}
                  {task.logs?.length ? (
                    <div className="mt-3 rounded-lg bg-muted/40 p-2 text-xs text-muted-foreground">
                      {task.logs.slice(-2).map((log, i) => (
                        <p key={i}>{log.message}</p>
                      ))}
                    </div>
                  ) : null}
                  <div className="mt-3 flex justify-end gap-2">
                    {task.status === "running" ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => void cancelAgentTask(task.id).then(() => refresh())}
                      >
                        取消
                      </Button>
                    ) : null}
                    {task.status === "failed" ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => void retryAgentTask(task.id).then(() => refresh())}
                      >
                        重试
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <aside className="w-full shrink-0 space-y-4 lg:w-[340px] lg:border-l lg:border-border/60 lg:pl-4">
          <div className="rounded-xl border border-border/60 bg-card p-4">
            <p className="text-sm font-medium">执行计划</p>
            {plan ? (
              <div className="mt-3 space-y-3 text-sm">
                <p className="text-muted-foreground">
                  意图：<span className="text-foreground">{plan.intent}</span>
                </p>
                <ol className="list-inside list-decimal space-y-1 text-muted-foreground">
                  {plan.steps.map((s) => (
                    <li key={s.order}>{s.title}</li>
                  ))}
                </ol>
                <div className="rounded-lg bg-muted/50 p-3 text-xs space-y-2">
                  <p>预计影响：{plan.impact}</p>
                  <div className="flex items-center gap-2">
                    <RiskBadge level={plan.risk} />
                    <span>{plan.riskReason}</span>
                  </div>
                </div>
                {plan.risk === "high" ? (
                  <input
                    value={confirmText}
                    onChange={(e) => setConfirmText(e.target.value)}
                    placeholder='输入 CONFIRM 确认'
                    className="h-8 w-full rounded-lg border border-input px-2 text-xs"
                  />
                ) : null}
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => {
                      setPlan(null);
                      setConfirmText("");
                    }}
                  >
                    取消
                  </Button>
                  <Button
                    size="sm"
                    className="flex-1"
                    disabled={loading}
                    onClick={() => void handleExecute()}
                  >
                    确认执行
                  </Button>
                </div>
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">
                输入自然语言任务后，将在此展示执行计划与风险确认。
              </p>
            )}
          </div>
        </aside>
      </div>

      <div className="mt-4 space-y-3 border-t border-border/60 pt-4">
        <div className="flex flex-wrap gap-2">
          {agentQuickChips.map((chip) => (
            <button
              key={chip.label}
              type="button"
              disabled={loading}
              onClick={() => {
                setInput(chip.label);
                void handlePlan(chip.label);
              }}
              className="rounded-full border border-border/60 px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-border hover:text-foreground disabled:opacity-50"
            >
              {chip.label}
              {chip.risk === "high" ? (
                <span className="ml-1 text-red-500">高</span>
              ) : null}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入自然语言任务，如：同步浙江大学专业..."
            className="min-h-[44px] resize-none"
            rows={1}
            disabled={loading}
          />
          <Button
            size="icon"
            className="shrink-0"
            disabled={loading}
            onClick={() => void handlePlan(input)}
            aria-label="发送"
          >
            <Send className="size-4" />
          </Button>
        </div>
      </div>
    </AdminPage>
  );
}
