"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  FileStack,
  History,
  LayoutTemplate,
  Loader2,
  Plus,
  RefreshCw,
  XCircle,
} from "lucide-react";

import {
  getAgentTaskDetail,
  listAgentTasks,
  type AgentTaskDetail,
  type AgentTaskSummary,
} from "@/lib/api/agent";
import { resolveUploadUrl } from "@/lib/config/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { AgentStepList, AgentFileList } from "@/components/chat/agent-step-list";
import type { AgentFile, AgentStep } from "@/lib/api/types";

function formatDate(iso: string): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** 任务列表项 */
function TaskRow({
  task,
  onClick,
}: {
  task: AgentTaskSummary;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-lg border border-border bg-card px-3 py-2.5 text-left transition-colors hover:bg-muted/50"
    >
      <span
        className={
          task.success
            ? "text-green-500"
            : "text-red-500"
        }
      >
        {task.success ? (
          <CheckCircle2 className="size-4" />
        ) : (
          <XCircle className="size-4" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-foreground">
          {task.user_input || "(无输入)"}
        </p>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
          <Clock className="size-3" />
          {formatDate(task.started_at)}
          <span>·</span>
          <span>{task.steps_count} 步</span>
        </div>
      </div>
      <Badge variant={task.success ? "default" : "destructive"}>
        {task.success ? "成功" : "失败"}
      </Badge>
    </button>
  );
}

/** 任务详情弹窗 */
function TaskDetailDialog({
  taskId,
  onClose,
}: {
  taskId: string | null;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<AgentTaskDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!taskId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getAgentTaskDetail(taskId)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((e) => {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "加载失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [taskId]);

  return (
    <Dialog open={!!taskId} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>任务执行详情</DialogTitle>
        </DialogHeader>
        {loading && (
          <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            加载中…
          </div>
        )}
        {error && (
          <div className="flex items-center gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <AlertCircle className="size-4" />
            {error}
          </div>
        )}
        {detail && !loading && (
          <div className="space-y-4">
            <div>
              <p className="text-xs text-muted-foreground">用户输入</p>
              <p className="mt-1 text-sm text-foreground">
                {detail.user_input || "(无输入)"}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <Badge variant="outline">
                  {detail.success ? "成功" : "失败"}
                </Badge>
                <span>耗时 {(detail.total_duration_ms / 1000).toFixed(1)}s</span>
                <span>·</span>
                <span>{detail.started_at ? formatDate(detail.started_at) : ""}</span>
              </div>
              {detail.error && (
                <p className="mt-2 rounded bg-destructive/10 px-2 py-1 text-xs text-destructive">
                  {detail.error}
                </p>
              )}
            </div>

            {detail.steps.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium text-muted-foreground">
                  工具调用步骤（{detail.steps.length}）
                </p>
                <AgentStepList
                  steps={detail.steps.map((s) => ({
                    step_id: s.step_id,
                    tool: s.tool_name,
                    args: s.args,
                    result: s.result,
                    status: s.status === "error" ? "running" : "done",
                  })) as AgentStep[]}
                />
              </div>
            )}

            {detail.files_generated.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium text-muted-foreground">
                  生成文件
                </p>
                <AgentFileList
                  files={detail.files_generated.map((f) => ({
                    filename: f.filename,
                    file_url: f.file_url,
                    file_path: f.file_path,
                    file_size: f.file_size,
                    format: f.format,
                    title: f.title,
                  })) as AgentFile[]}
                />
              </div>
            )}

            {detail.final_output && (
              <div>
                <p className="mb-1 text-xs font-medium text-muted-foreground">
                  最终输出
                </p>
                <pre className="max-h-60 overflow-y-auto rounded-lg bg-muted/40 p-3 text-xs whitespace-pre-wrap text-foreground/80">
                  {detail.final_output.slice(0, 2000)}
                </pre>
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function AgentWorkbenchClient() {
  const [tasks, setTasks] = useState<AgentTaskSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAgentTasks(30);
      setTasks(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载任务列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Agent 工作台</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            商业级通用任务 Agent · 全链路审计 · 模板强约束 · 批量执行
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={loadTasks} disabled={loading}>
          <RefreshCw className="size-4" />
          刷新
        </Button>
      </div>

      {/* 入口卡片 */}
      <div className="grid gap-3 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="mb-2 flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <FileStack className="size-[18px]" />
            </div>
            <CardTitle>批量任务</CardTitle>
            <CardDescription>
              上传多份文档 + 指令，Agent 逐项生成（Celery 异步）
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/agent/batch">
              <Button className="w-full">
                <Plus className="size-4" />
                发起批量
              </Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="mb-2 flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <LayoutTemplate className="size-[18px]" />
            </div>
            <CardTitle>模板管理</CardTitle>
            <CardDescription>
              维护文档模板与校验规则，Agent 导出前按模板强约束生成
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/agent/templates">
              <Button variant="outline" className="w-full">
                管理模板
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* 任务历史 */}
      <div>
        <div className="mb-3 flex items-center gap-2">
          <History className="size-4 text-muted-foreground" />
          <h2 className="text-sm font-medium">任务历史</h2>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <AlertCircle className="size-4" />
            {error}
          </div>
        )}

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : tasks.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center gap-2 py-12 text-center">
              <History className="size-8 text-muted-foreground/40" />
              <p className="text-sm text-muted-foreground">暂无任务记录</p>
              <p className="text-xs text-muted-foreground/60">
                前往聊天页使用 Agent 模式，或发起批量任务
              </p>
              <Link href="/chat">
                <Button variant="outline" size="sm" className="mt-2">
                  打开对话
                </Button>
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            {tasks.map((task) => (
              <TaskRow
                key={task.task_id}
                task={task}
                onClick={() => setSelectedTaskId(task.task_id)}
              />
            ))}
          </div>
        )}
      </div>

      <TaskDetailDialog
        taskId={selectedTaskId}
        onClose={() => setSelectedTaskId(null)}
      />
    </div>
  );
}
