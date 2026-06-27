"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  CheckCircle2,
  FileStack,
  FileUp,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
  XCircle,
} from "lucide-react";

import {
  fetchAgentBatchStatus,
  submitAgentBatch,
  type BatchItemSpec,
  type BatchStatusRecord,
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
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";

/** 单个批量项：指令 + 可选文件 */
type BatchItem = {
  /** 前端临时 ID（用于 React key） */
  uid: string;
  instruction: string;
  file: File | null;
};

let _uidSeq = 0;
function nextUid(): string {
  _uidSeq += 1;
  return `item_${Date.now()}_${_uidSeq}`;
}

function makeEmptyItem(): BatchItem {
  return { uid: nextUid(), instruction: "", file: null };
}

const ACCEPTED_EXTS = ".pdf,.docx,.txt,.md,.markdown,.csv,.xlsx";

export function AgentBatchClient() {
  const [items, setItems] = useState<BatchItem[]>([makeEmptyItem()]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 提交后的任务进度
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<BatchStatusRecord | null>(null);
  const [polling, setPolling] = useState(false);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── 编辑器操作 ────────────────────────────────────────────

  const addItem = () => {
    setItems((prev) => [...prev, makeEmptyItem()]);
  };

  const removeItem = (uid: string) => {
    setItems((prev) =>
      prev.length > 1 ? prev.filter((it) => it.uid !== uid) : prev
    );
  };

  const updateInstruction = (uid: string, value: string) => {
    setItems((prev) =>
      prev.map((it) => (it.uid === uid ? { ...it, instruction: value } : it))
    );
  };

  const updateFile = (uid: string, file: File | null) => {
    setItems((prev) =>
      prev.map((it) => (it.uid === uid ? { ...it, file } : it))
    );
  };

  // ── 提交 ────────────────────────────────────────────────

  const canSubmit =
    !submitting &&
    items.some((it) => it.instruction.trim().length > 0) &&
    items.length <= 50;

  const handleSubmit = async () => {
    setError(null);
    const validItems = items.filter((it) => it.instruction.trim().length > 0);
    if (validItems.length === 0) {
      setError("至少需要一项指令");
      return;
    }
    if (validItems.length > 50) {
      setError("单次最多 50 项任务");
      return;
    }

    // 收集所有文件到扁平数组，记录每项的 file_index
    const files: File[] = [];
    const specs: BatchItemSpec[] = validItems.map((it) => {
      let file_index: number | undefined;
      if (it.file) {
        file_index = files.length;
        files.push(it.file);
      }
      return {
        instruction: it.instruction.trim(),
        file_index,
      };
    });

    setSubmitting(true);
    try {
      const res = await submitAgentBatch(files, specs);
      setTaskId(res.task_id);
      setStatus(null);
      setPolling(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  // ── 轮询进度 ────────────────────────────────────────────

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setPolling(false);
  }, []);

  const pollOnce = useCallback(
    async (id: string) => {
      try {
        const record = await fetchAgentBatchStatus(id);
        setStatus(record);
        if (record.status === "done" || record.status === "failed") {
          stopPolling();
          return;
        }
      } catch (e) {
        // 轮询失败不立即终止，下次重试
        console.warn("轮询批量状态失败:", e);
      }
      pollTimerRef.current = setTimeout(() => void pollOnce(id), 2000);
    },
    [stopPolling]
  );

  useEffect(() => {
    if (!taskId || !polling) return;
    void pollOnce(taskId);
    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [taskId, polling, pollOnce]);

  const handleReset = () => {
    stopPolling();
    setTaskId(null);
    setStatus(null);
    setItems([makeEmptyItem()]);
    setError(null);
  };

  const handleRefreshStatus = () => {
    if (taskId) void pollOnce(taskId);
  };

  // ── 渲染 ────────────────────────────────────────────────

  const isRunning = status?.status === "running" || status?.status === "pending";
  const result = status?.result;

  return (
    <div className="mx-auto max-w-4xl space-y-5 p-4 md:p-6">
      {/* 头部 */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Link href="/agent" className="hover:text-foreground">
              Agent 工作台
            </Link>
            <span>/</span>
            <span>批量任务</span>
          </div>
          <h1 className="mt-1 flex items-center gap-2 text-xl font-semibold tracking-tight">
            <FileStack className="size-5" />
            批量任务
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            上传多份文档 + 指令，Agent 逐项异步生成（Celery 后台执行）
          </p>
        </div>
        {taskId && (
          <Button variant="ghost" size="sm" onClick={handleReset}>
            新建批次
          </Button>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="size-4" />
          {error}
        </div>
      )}

      {/* 编辑器（未提交或已重置时显示） */}
      {!taskId && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">任务清单</CardTitle>
            <CardDescription>
              每项可附加一份文档（可选），指令必填。最多 50 项。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {items.map((it, idx) => (
              <div
                key={it.uid}
                className="rounded-lg border border-border bg-muted/30 p-3 space-y-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-muted-foreground">
                    #{idx + 1}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    onClick={() => removeItem(it.uid)}
                    disabled={items.length === 1}
                    aria-label="删除该项"
                    className="text-destructive hover:text-destructive"
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
                <div className="space-y-1">
                  <Label htmlFor={`inst-${it.uid}`} className="text-xs">
                    指令
                  </Label>
                  <Textarea
                    id={`inst-${it.uid}`}
                    value={it.instruction}
                    onChange={(e) => updateInstruction(it.uid, e.target.value)}
                    rows={2}
                    placeholder="如：基于上传文件生成一份学术论文，导出 PDF"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">附件（可选）</Label>
                  <div className="flex items-center gap-2">
                    <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-input bg-background px-2.5 py-1.5 text-xs hover:bg-muted transition-colors">
                      <FileUp className="size-3.5" />
                      {it.file ? "更换文件" : "选择文件"}
                      <input
                        type="file"
                        accept={ACCEPTED_EXTS}
                        className="hidden"
                        onChange={(e) =>
                          updateFile(it.uid, e.target.files?.[0] ?? null)
                        }
                      />
                    </label>
                    {it.file && (
                      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <CheckCircle2 className="size-3.5 text-green-500" />
                        {it.file.name}
                        <span className="text-muted-foreground/60">
                          ({(it.file.size / 1024).toFixed(1)} KB)
                        </span>
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}

            <div className="flex items-center justify-between pt-1">
              <Button variant="outline" size="sm" onClick={addItem}>
                <Plus className="size-4" />
                添加一项
              </Button>
              <Button onClick={handleSubmit} disabled={!canSubmit}>
                {submitting && <Loader2 className="size-4 animate-spin" />}
                提交批量任务
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 进度卡片（提交后显示） */}
      {taskId && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm">执行进度</CardTitle>
                  <CardDescription className="mt-1 font-mono text-xs">
                    task_id: {taskId}
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      status?.status === "done"
                        ? "default"
                        : status?.status === "failed"
                          ? "destructive"
                          : "secondary"
                    }
                  >
                    {status?.status_label ?? "等待中"}
                  </Badge>
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    onClick={handleRefreshStatus}
                    disabled={!polling && status?.status !== "running"}
                    aria-label="刷新"
                  >
                    <RefreshCw
                      className={polling ? "size-3.5 animate-spin" : "size-3.5"}
                    />
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>
                    {status?.message || (isRunning ? "处理中…" : "")}
                  </span>
                  <span>{status?.progress ?? 0}%</span>
                </div>
                <Progress value={status?.progress ?? 0} />
              </div>

              {status?.error && (
                <div className="rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">
                  {status.error}
                </div>
              )}

              {result && (
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>
                    总计 <strong className="text-foreground">{result.total}</strong>
                  </span>
                  <span className="text-green-600 dark:text-green-400">
                    成功 <strong>{result.success}</strong>
                  </span>
                  <span className="text-red-500">
                    失败 <strong>{result.failed}</strong>
                  </span>
                </div>
              )}
            </CardContent>
          </Card>

          {/* 单项结果列表 */}
          {result && result.items.length > 0 && (
            <div className="space-y-2">
              <h2 className="text-sm font-medium">单项结果</h2>
              {result.items.map((item) => (
                <Card key={item.index}>
                  <CardContent className="py-3 space-y-1.5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">
                            #{item.index + 1}
                          </span>
                          {item.ok ? (
                            <CheckCircle2 className="size-3.5 text-green-500" />
                          ) : (
                            <XCircle className="size-3.5 text-red-500" />
                          )}
                          {item.file_name && (
                            <Badge variant="outline" className="text-[10px]">
                              {item.file_name}
                            </Badge>
                          )}
                        </div>
                        <p className="mt-1 truncate text-xs text-foreground">
                          {item.instruction}
                        </p>
                      </div>
                      {item.task_id && (
                        <Link
                          href={`/agent?task=${item.task_id}`}
                          className="shrink-0 text-xs text-primary hover:underline"
                        >
                          查看详情
                        </Link>
                      )}
                    </div>

                    {item.error && (
                      <p className="rounded bg-destructive/10 px-2 py-1 text-xs text-destructive">
                        {item.error}
                      </p>
                    )}

                    {item.files && item.files.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {item.files.map((f, i) => {
                          const url = f.file_url
                            ? resolveUploadUrl(f.file_url)
                            : null;
                          if (!url) return null;
                          return (
                            <a
                              key={i}
                              href={url}
                              download={f.filename}
                              className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/40 px-2 py-1 text-xs hover:bg-muted transition-colors"
                            >
                              <FileUp className="size-3 text-primary" />
                              {f.title || f.filename || "下载文件"}
                            </a>
                          );
                        })}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
