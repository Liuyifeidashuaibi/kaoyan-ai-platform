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
import { fetchAdminModeration } from "@/lib/admin/api/community";
import { useAdminList } from "@/hooks/use-admin-list";

const nav = adminNavItems.find((item) => item.id === "community")!;

export function ModerationListClient() {
  const fetcher = useCallback(
    (p: { page: number; pageSize: number }) =>
      fetchAdminModeration({ page: p.page, pageSize: p.pageSize }),
    []
  );
  const { page, setPage, loading, error, items, total, pageSize, reload } = useAdminList({
    fetcher: (p) => fetcher(p),
  });

  return (
    <AdminModulePage title="内容审核" description="待复核的隐藏帖子" subNav={nav.children}>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <AdminDataTableShell>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>标题</TableHead>
              <TableHead>互动</TableHead>
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
              : items.map((post) => (
                  <TableRow key={post.id}>
                    <TableCell className="max-w-sm truncate font-medium">{post.title}</TableCell>
                    <TableCell className="text-muted-foreground tabular-nums">
                      {post.comment_count} / {post.favorite_count}
                    </TableCell>
                    <TableCell>
                      <Badge variant="destructive">已隐藏</Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatAdminDate(post.created_at)}
                    </TableCell>
                    <TableCell>
                      <PostRowActions
                        postId={post.id}
                        isHidden
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
