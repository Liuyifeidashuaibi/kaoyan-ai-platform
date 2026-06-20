"use client";

import { useCallback, useState } from "react";
import Link from "next/link";

import { BatchModerateBar } from "@/components/admin/community/batch-moderate-bar";
import { PostRowActions } from "@/components/admin/community/post-row-actions";
import { AdminModulePage } from "@/components/admin/layout/admin-module-page";
import {
  AdminDataTableShell,
  AdminTableFooter,
  formatAdminDate,
} from "@/components/admin/data-table/admin-data-table";
import { FilterBar } from "@/components/admin/shared/filter-bar";
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
import { fetchAdminPosts, type AdminPost } from "@/lib/admin/api/community";

const nav = adminNavItems.find((item) => item.id === "community")!;

export function PostsListClient() {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const fetcher = useCallback(
    (p: { page: number; pageSize: number; q: string }) =>
      fetchAdminPosts({ page: p.page, pageSize: p.pageSize, q: p.q }),
    []
  );

  const { q, setQ, page, setPage, loading, error, items, total, pageSize, search, reload } =
    useAdminList<AdminPost>({ fetcher });

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <AdminModulePage
      title="社区中心"
      description="帖子、评论与内容审核"
      subNav={nav.children}
      actions={
        <Badge variant="outline" className="font-normal">
          {total} 帖子
        </Badge>
      }
    >
      <FilterBar value={q} onChange={setQ} onSearch={search} placeholder="搜索标题" />

      <BatchModerateBar
        selectedIds={[...selected]}
        onClear={() => setSelected(new Set())}
        onDone={() => {
          setSelected(new Set());
          void reload();
        }}
      />

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <AdminDataTableShell>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10" />
              <TableHead>标题</TableHead>
              <TableHead>类型</TableHead>
              <TableHead>互动</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>发布时间</TableHead>
              <TableHead className="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={7}>
                      <Skeleton className="h-8 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              : items.map((post) => (
                  <TableRow key={post.id}>
                    <TableCell>
                      <input
                        type="checkbox"
                        checked={selected.has(post.id)}
                        onChange={() => toggle(post.id)}
                        className="size-4 rounded border-border"
                      />
                    </TableCell>
                    <TableCell className="max-w-[240px] truncate font-medium">
                      <Link
                        href={`/admin/community/posts/${post.id}`}
                        className="hover:underline"
                      >
                        {post.title}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{post.post_type}</TableCell>
                    <TableCell className="tabular-nums text-muted-foreground">
                      {post.view_count} / {post.comment_count} / {post.favorite_count}
                    </TableCell>
                    <TableCell>
                      <Badge variant={post.is_hidden ? "destructive" : "outline"}>
                        {post.is_hidden ? "隐藏" : "正常"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatAdminDate(post.created_at)}
                    </TableCell>
                    <TableCell>
                      <PostRowActions
                        postId={post.id}
                        isHidden={post.is_hidden}
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
