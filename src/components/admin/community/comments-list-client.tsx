"use client";

import { useCallback } from "react";
import Link from "next/link";

import { AdminModulePage } from "@/components/admin/layout/admin-module-page";
import {
  AdminDataTableShell,
  AdminTableFooter,
  formatAdminDate,
} from "@/components/admin/data-table/admin-data-table";
import { FilterBar } from "@/components/admin/shared/filter-bar";
import { Button } from "@/components/ui/button";
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
import { useAdminToast } from "@/components/admin/shared/admin-toast";
import { deleteAdminComment, fetchAdminComments } from "@/lib/admin/api/community";
import { useAdminList } from "@/hooks/use-admin-list";

const nav = adminNavItems.find((item) => item.id === "community")!;

export function CommentsListClient() {
  const { toast } = useAdminToast();
  const fetcher = useCallback(
    (p: { page: number; pageSize: number; q: string }) =>
      fetchAdminComments({ page: p.page, pageSize: p.pageSize, q: p.q }),
    []
  );
  const { q, setQ, page, setPage, loading, error, items, total, pageSize, search, reload } =
    useAdminList({ fetcher });

  async function handleDelete(commentId: string) {
    if (!window.confirm("确定删除该评论？")) return;
    try {
      await deleteAdminComment(commentId);
      toast("评论已删除", "success");
      await reload();
    } catch (e) {
      toast(e instanceof Error ? e.message : "删除失败", "error");
    }
  }

  return (
    <AdminModulePage title="评论管理" subNav={nav.children}>
      <FilterBar value={q} onChange={setQ} onSearch={search} placeholder="搜索评论内容" />
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <AdminDataTableShell>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>内容</TableHead>
              <TableHead>帖子</TableHead>
              <TableHead>作者</TableHead>
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
              : items.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="max-w-md truncate">{c.content}</TableCell>
                    <TableCell>
                      <Link
                        href={`/admin/community/posts/${c.post_id}`}
                        className="font-mono text-xs text-muted-foreground hover:text-foreground"
                      >
                        查看帖子
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Link
                        href={`/admin/users/${c.author_id}`}
                        className="font-mono text-xs text-muted-foreground hover:text-foreground"
                      >
                        查看用户
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatAdminDate(c.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => void handleDelete(c.id)}
                      >
                        删除
                      </Button>
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
