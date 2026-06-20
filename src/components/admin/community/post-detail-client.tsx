"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AdminPage } from "@/components/admin/layout/admin-shell";
import { AdminPageHeader } from "@/components/admin/layout/admin-page-header";
import { PostRowActions } from "@/components/admin/community/post-row-actions";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchAdminPostDetail } from "@/lib/admin/api/community";
import { ApiError } from "@/lib/api/client";
import { formatAdminDate } from "@/components/admin/data-table/admin-data-table";

export function PostDetailClient({ postId }: { postId: string }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [post, setPost] = useState<Awaited<ReturnType<typeof fetchAdminPostDetail>> | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    fetchAdminPostDetail(postId)
      .then(setPost)
      .catch((e) => setError(e instanceof ApiError ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [postId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <AdminPage>
      <div className="space-y-6">
        <AdminPageHeader
          title={post?.title ?? "帖子详情"}
          description={post ? `${post.post_type} · ${post.subject_category}` : undefined}
          actions={
            <Link href="/admin/community/posts" className="text-sm text-muted-foreground hover:text-foreground">
              返回列表
            </Link>
          }
        />

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        {loading ? (
          <Skeleton className="h-64 rounded-xl" />
        ) : post ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={post.is_hidden ? "destructive" : "outline"}>
                {post.is_hidden ? "已隐藏" : "正常"}
              </Badge>
              <span className="text-sm text-muted-foreground">
                {formatAdminDate(post.created_at)} · 浏览 {post.view_count}
              </span>
              {post.author ? (
                <Link
                  href={`/admin/users/${post.author.id}`}
                  className="text-sm text-muted-foreground hover:text-foreground"
                >
                  作者：{post.author.nickname || post.author.email}
                </Link>
              ) : null}
            </div>

            <div className="rounded-xl border border-border/60 bg-card p-6">
              <div className="prose prose-sm max-w-none whitespace-pre-wrap text-sm">
                {post.content || "（无正文）"}
              </div>
            </div>

            <div className="flex justify-end">
              <PostRowActions postId={post.id} isHidden={post.is_hidden} onDone={load} />
            </div>

            {post.recent_comments?.length ? (
              <div className="rounded-xl border border-border/60 bg-card p-4">
                <p className="mb-3 text-sm font-medium">最近评论</p>
                <ul className="space-y-3">
                  {post.recent_comments.map((c) => (
                    <li key={c.id} className="border-b border-border/40 pb-3 last:border-0 last:pb-0">
                      <p className="text-sm">{c.content}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {formatAdminDate(c.created_at)}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </AdminPage>
  );
}
