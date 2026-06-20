"use client";

import { useCallback } from "react";

import { PostRowActions } from "@/components/admin/community/post-row-actions";
import { AdminModulePage } from "@/components/admin/layout/admin-module-page";
import {
  AdminDataTableShell,
  AdminTableFooter,
  formatAdminDate,
} from "@/components/admin/data-table/admin-data-table";
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
import { fetchAdminReports } from "@/lib/admin/api/community";
import { useAdminList } from "@/hooks/use-admin-list";

const nav = adminNavItems.find((item) => item.id === "community")!;

export function ReportsListClient() {
  const fetcher = useCallback(
    (p: { page: number; pageSize: number }) =>
      fetchAdminReports({ page: p.page, pageSize: p.pageSize }),
    []
  );
  const { page, setPage, loading, error, items, total, pageSize, reload } = useAdminList({
    fetcher: (p) => fetcher(p),
  });

  return (
    <AdminModulePage
      title="举报管理"
      description="当前以隐藏帖子作为举报待办来源"
      subNav={nav.children}
    >
      <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-muted-foreground">
        说明：数据库暂无独立举报表，本页展示的是<strong className="text-foreground">已隐藏帖子</strong>
        ，与「内容审核」数据源相同，用于运营快速处理。
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <AdminDataTableShell>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>帖子</TableHead>
              <TableHead>原因</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>时间</TableHead>
              <TableHead className="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={5}><Skeleton className="h-8 w-full" /></TableCell>
                  </TableRow>
                ))
              : items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="max-w-sm truncate font-medium">{item.title}</TableCell>
                    <TableCell className="text-muted-foreground">{item.reason ?? "—"}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{item.status ?? "pending"}</Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatAdminDate(item.created_at)}
                    </TableCell>
                    <TableCell>
                      <PostRowActions
                        postId={item.id}
                        isHidden={item.is_hidden}
                        onDone={() => void reload()}
                        compact
                      />
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
