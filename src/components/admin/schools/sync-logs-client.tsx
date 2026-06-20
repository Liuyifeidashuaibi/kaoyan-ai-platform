"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";

import { AdminModulePage } from "@/components/admin/layout/admin-module-page";
import {
  AdminDataTableShell,
  AdminTableFooter,
  formatAdminDate,
} from "@/components/admin/data-table/admin-data-table";
import { useAdminToast } from "@/components/admin/shared/admin-toast";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { adminNavItems } from "@/config/admin-navigation";
import { useAdminList } from "@/hooks/use-admin-list";
import { createAgentPlan } from "@/lib/admin/api/agents";
import { fetchSyncLogs, type SyncLogsResponse } from "@/lib/admin/api/schools";

const nav = adminNavItems.find((item) => item.id === "schools")!;

export function SyncLogsClient() {
  const router = useRouter();
  const { toast } = useAdminToast();
  const [meta, setMeta] = useState<SyncLogsResponse["meta"]>(null);

  const fetcher = useCallback(async (p: { page: number; pageSize: number }) => {
    const res = await fetchSyncLogs({ page: p.page, pageSize: p.pageSize });
    setMeta(res?.meta ?? null);
    return res;
  }, []);

  const { page, setPage, loading, error, items, total, pageSize } = useAdminList({
    fetcher: (p) => fetcher(p),
  });

  return (
    <AdminModulePage
      title="数据同步记录"
      subNav={nav.children}
      actions={
        <Button
          size="sm"
          onClick={async () => {
            try {
              await createAgentPlan("同步招生公告");
              toast("已创建同步任务，请前往 Agent 中心确认执行", "success");
              router.push("/admin/agents");
            } catch (e) {
              toast(e instanceof Error ? e.message : "创建失败", "error");
            }
          }}
        >
          新建同步任务
        </Button>
      }
    >
      {meta ? (
        <div className="mb-4 rounded-xl border border-border/60 bg-card p-4 text-sm">
          <div className="flex flex-wrap items-center gap-3">
            <span>
              当前版本 <strong className="tabular-nums">{meta.revision}</strong>
            </span>
            <span className="text-muted-foreground">
              更新于 {formatAdminDate(meta.updated_at)}
            </span>
            {meta.note ? <span className="text-muted-foreground">{meta.note}</span> : null}
          </div>
        </div>
      ) : null}

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <AdminDataTableShell>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>页面</TableHead>
              <TableHead>类型</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>最近抓取</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={4}>
                      <Skeleton className="h-8 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              : items.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="max-w-sm">
                      <div className="truncate font-medium">{row.title || row.url}</div>
                      <div className="truncate text-xs text-muted-foreground">{row.url}</div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{row.page_type || "—"}</TableCell>
                    <TableCell>
                      <Badge variant={row.status === "ok" ? "secondary" : "outline"}>
                        {row.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {row.last_fetch_time
                        ? formatAdminDate(row.last_fetch_time)
                        : formatAdminDate(row.updated_at)}
                    </TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
        <AdminTableFooter total={total} page={page} pageSize={pageSize} onPageChange={setPage} />
      </AdminDataTableShell>
    </AdminModulePage>
  );
}
