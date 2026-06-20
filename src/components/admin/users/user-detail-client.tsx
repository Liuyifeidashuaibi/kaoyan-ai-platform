"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { AdminPage } from "@/components/admin/layout/admin-shell";
import { AdminPageHeader } from "@/components/admin/layout/admin-page-header";
import { MetricCard } from "@/components/admin/shared/metric-card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  fetchAdminUserDetail,
  fetchAdminUserFavoritesFor,
  fetchAdminUserFollowsFor,
  fetchAdminUserPosts,
  type AdminUserDetail,
} from "@/lib/admin/api/users";
import { ApiError } from "@/lib/api/client";
import { formatAdminDate } from "@/components/admin/data-table/admin-data-table";

export function UserDetailClient({ userId }: { userId: string }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<AdminUserDetail | null>(null);
  const [tab, setTab] = useState("overview");
  const [posts, setPosts] = useState<{ id: string; title: string; is_hidden: boolean; created_at: string }[]>([]);
  const [follows, setFollows] = useState<{ following_id: string; created_at: string }[]>([]);
  const [favorites, setFavorites] = useState<{ post_id: string; created_at: string }[]>([]);

  useEffect(() => {
    fetchAdminUserDetail(userId)
      .then(setUser)
      .catch((e) => setError(e instanceof ApiError ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [userId]);

  useEffect(() => {
    if (tab === "posts") {
      fetchAdminUserPosts(userId).then((r) => setPosts(r?.items ?? []));
    }
    if (tab === "follows") {
      fetchAdminUserFollowsFor(userId).then((r) => setFollows(r?.items ?? []));
    }
    if (tab === "favorites") {
      fetchAdminUserFavoritesFor(userId).then((r) => setFavorites(r?.items ?? []));
    }
  }, [tab, userId]);

  return (
    <AdminPage>
      <div className="space-y-6">
        <AdminPageHeader
          title={user?.nickname || "用户详情"}
          description={user?.email ?? `用户 ID: ${userId}`}
          actions={
            <Link href="/admin/users" className="text-sm text-muted-foreground hover:text-foreground">
              返回列表
            </Link>
          }
        />

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        {loading ? (
          <Skeleton className="h-48 rounded-xl" />
        ) : user ? (
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="overview">概览</TabsTrigger>
              <TabsTrigger value="posts">发帖</TabsTrigger>
              <TabsTrigger value="follows">关注</TabsTrigger>
              <TabsTrigger value="favorites">收藏</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="mt-6 space-y-6">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard label="发帖" value={user.stats.posts} />
                <MetricCard label="粉丝" value={user.stats.followers} />
                <MetricCard label="关注" value={user.stats.following} />
                <MetricCard label="收藏" value={user.stats.favorites} />
              </div>
              <div className="rounded-xl border border-border/60 bg-card p-6 text-sm space-y-2">
                <p><span className="text-muted-foreground">昵称：</span>{user.nickname || "—"}</p>
                <p><span className="text-muted-foreground">邮箱：</span>{user.email || "—"}</p>
                <p><span className="text-muted-foreground">目标年份：</span>{user.target_year ?? "—"}</p>
                <p><span className="text-muted-foreground">注册时间：</span>{formatAdminDate(user.created_at)}</p>
                {user.bio ? <p><span className="text-muted-foreground">简介：</span>{user.bio}</p> : null}
              </div>
            </TabsContent>

            <TabsContent value="posts" className="mt-6">
              <ul className="divide-y divide-border/60 rounded-xl border border-border/60 bg-card">
                {posts.length === 0 ? (
                  <li className="p-6 text-center text-sm text-muted-foreground">暂无帖子</li>
                ) : (
                  posts.map((p) => (
                    <li key={p.id} className="flex items-center justify-between px-4 py-3">
                      <Link href={`/admin/community/posts/${p.id}`} className="text-sm font-medium hover:underline">
                        {p.title}
                      </Link>
                      <span className="text-xs text-muted-foreground">{formatAdminDate(p.created_at)}</span>
                    </li>
                  ))
                )}
              </ul>
            </TabsContent>

            <TabsContent value="follows" className="mt-6">
              <ul className="divide-y divide-border/60 rounded-xl border border-border/60 bg-card">
                {follows.map((f) => (
                  <li key={f.following_id} className="flex justify-between px-4 py-3 text-sm">
                    <Link href={`/admin/users/${f.following_id}`} className="font-mono text-xs hover:underline">
                      {f.following_id.slice(0, 8)}…
                    </Link>
                    <span className="text-muted-foreground">{formatAdminDate(f.created_at)}</span>
                  </li>
                ))}
              </ul>
            </TabsContent>

            <TabsContent value="favorites" className="mt-6">
              <ul className="divide-y divide-border/60 rounded-xl border border-border/60 bg-card">
                {favorites.map((f) => (
                  <li key={f.post_id} className="flex justify-between px-4 py-3 text-sm">
                    <Link href={`/admin/community/posts/${f.post_id}`} className="font-mono text-xs hover:underline">
                      帖子 {f.post_id.slice(0, 8)}…
                    </Link>
                    <span className="text-muted-foreground">{formatAdminDate(f.created_at)}</span>
                  </li>
                ))}
              </ul>
            </TabsContent>
          </Tabs>
        ) : null}
      </div>
    </AdminPage>
  );
}
