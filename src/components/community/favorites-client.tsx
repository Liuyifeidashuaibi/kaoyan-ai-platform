"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Loader2, Star } from "lucide-react";

import { PostCard } from "@/components/community/post-card";
import { Button, buttonVariants } from "@/components/ui/button";
import { listFavorites, toggleFavorite } from "@/lib/api/community";
import type { CommunityPost } from "@/lib/api/types";
import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";

export function FavoritesClient() {
  const [posts, setPosts] = useState<CommunityPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    if (!isSupabaseConfigured()) return;
    const supabase = createClient();
    void supabase.auth.getUser().then(({ data }) => {
      setCurrentUserId(data.user?.id ?? null);
    });
  }, []);

  const loadFavorites = useCallback(async (pageNum: number, append = false) => {
    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
      setError(null);
    }
    try {
      const data = await listFavorites(pageNum);
      setPosts((prev) => (append ? [...prev, ...data.items] : data.items));
      setPage(pageNum);
      setHasMore(data.has_more);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
      if (!append) setPosts([]);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    void loadFavorites(1);
  }, [loadFavorites]);

  async function handleFavoriteToggle(postId: string) {
    const result = await toggleFavorite(postId);
    if (!result.favorited) {
      setPosts((prev) => prev.filter((p) => p.id !== postId));
      return;
    }
    setPosts((prev) =>
      prev.map((p) =>
        p.id === postId
          ? {
              ...p,
              is_favorited: true,
              favorite_count: Math.max(0, p.favorite_count + 1),
            }
          : p
      )
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Link href="/community" className={buttonVariants({ variant: "ghost", size: "icon-sm" })}>
            <ArrowLeft />
          </Link>
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
              <Star className="size-6" />
              我的收藏
            </h1>
            <p className="text-muted-foreground">点击帖子可打开原帖</p>
          </div>
        </div>
        <Link href="/community" className={buttonVariants({ variant: "outline", size: "sm" })}>
          返回社区
        </Link>
      </div>

      <div className="space-y-3">
        {loading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <p className="py-8 text-center text-destructive">{error}</p>
        ) : posts.length === 0 ? (
          <div className="py-16 text-center text-muted-foreground">
            <p>还没有收藏任何帖子</p>
            <Link href="/community" className="mt-2 inline-block underline">
              去社区逛逛
            </Link>
          </div>
        ) : (
          <>
            {posts.map((post) => (
              <PostCard
                key={post.id}
                post={post}
                canFavorite={!!currentUserId}
                onFavoriteToggle={handleFavoriteToggle}
              />
            ))}
            {hasMore && (
              <div className="flex justify-center pt-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={loadingMore}
                  onClick={() => void loadFavorites(page + 1, true)}
                >
                  {loadingMore ? <Loader2 className="animate-spin" /> : "加载更多"}
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
