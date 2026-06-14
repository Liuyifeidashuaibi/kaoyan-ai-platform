"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, Plus, Search, Star, Users } from "lucide-react";

import { CreatePostDialog } from "@/components/community/create-post-dialog";
import { PostCard } from "@/components/community/post-card";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { listPosts, searchCommunity, toggleFavorite } from "@/lib/api/community";
import type { CommunityPost } from "@/lib/api/types";
import { COMMUNITY_SORT_TABS, POST_TYPES, communityFavoritesHref, type PostType } from "@/lib/community/constants";
import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";

export function CommunityClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialSort = searchParams.get("sort") === "hot" ? "hot" : "latest";
  const initialCategory = searchParams.get("category") ?? "";
  const initialQ = searchParams.get("q") ?? "";

  const [sort, setSort] = useState<"latest" | "hot">(initialSort);
  const [postType, setPostType] = useState<PostType | "">("");
  const [subjectCategory, setSubjectCategory] = useState(initialCategory);
  const [search, setSearch] = useState(initialQ);
  const [posts, setPosts] = useState<CommunityPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (!isSupabaseConfigured()) return;
    const supabase = createClient();
    void supabase.auth.getUser().then(({ data }) => {
      setCurrentUserId(data.user?.id ?? null);
    });
  }, []);

  const loadPosts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listPosts({
        sort,
        post_type: postType || undefined,
        subject_category: subjectCategory || undefined,
        q: search.trim() || undefined,
      });
      setPosts(data.items);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "加载失败";
      setError(
        msg.includes("Supabase")
          ? "社区服务连接失败，请确认后端已重启"
          : msg
      );
    } finally {
      setLoading(false);
    }
  }, [sort, postType, subjectCategory, search]);

  useEffect(() => {
    void loadPosts();
  }, [loadPosts]);

  async function handleFavoriteToggle(postId: string) {
    const result = await toggleFavorite(postId);
    setPosts((prev) =>
      prev.map((p) =>
        p.id === postId
          ? {
              ...p,
              is_favorited: result.favorited,
              favorite_count: Math.max(
                0,
                p.favorite_count + (result.favorited ? 1 : -1)
              ),
            }
          : p
      )
    );
  }

  async function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = search.trim();
    if (!q) {
      void loadPosts();
      return;
    }
    try {
      const result = await searchCommunity(q);
      if (result.kind === "user" && result.display_id) {
        router.push(`/user/${result.display_id}`);
        return;
      }
      if (result.kind === "subject") {
        setSubjectCategory(result.subject_category);
        setSearch("");
        router.push(`/community?category=${encodeURIComponent(result.subject_category)}`);
        return;
      }
      if (result.kind === "posts") {
        setPosts(result.posts);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "搜索失败");
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">社区</h1>
          <p className="text-muted-foreground">分享备考经验与学习资料</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/following" className={buttonVariants({ variant: "outline", size: "sm" })}>
            <Users />
            关注
          </Link>
          <Link
            href={communityFavoritesHref()}
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            <Star />
            我的收藏
          </Link>
          {mounted && currentUserId ? (
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus />
              发帖
            </Button>
          ) : mounted ? (
            <Link
              href="/login?next=/community"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              登录后发帖
            </Link>
          ) : (
            <span
              className={buttonVariants({ variant: "outline", size: "sm" })}
              aria-hidden
            >
              ···
            </span>
          )}
        </div>
      </div>

      <form onSubmit={handleSearchSubmit} className="flex gap-2">
        <div className="relative min-w-0 flex-1">
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索用户 ID、专业大类或帖子内容…"
            className="pl-9"
          />
        </div>
        <Button type="submit" variant="secondary">
          搜索
        </Button>
      </form>

      <div className="flex flex-col gap-3">
        <Tabs
          value={sort}
          onValueChange={(v) => setSort(v as "latest" | "hot")}
        >
          <TabsList>
            {COMMUNITY_SORT_TABS.map((tab) => (
              <TabsTrigger key={tab.value} value={tab.value}>
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant={postType === "" ? "default" : "outline"}
              onClick={() => setPostType("")}
            >
              全部类型
            </Button>
            {POST_TYPES.map((t) => (
              <Button
                key={t.value}
                size="sm"
                variant={postType === t.value ? "default" : "outline"}
                onClick={() => setPostType(t.value)}
              >
                {t.label}
              </Button>
            ))}
          </div>

        {subjectCategory && (
          <p className="text-sm text-muted-foreground">
            筛选专业：{subjectCategory}
            <button
              type="button"
              className="ml-2 underline"
              onClick={() => {
                setSubjectCategory("");
                router.replace("/community");
              }}
            >
              清除
            </button>
          </p>
        )}

        <div className="space-y-3">
          {loading ? (
            <div className="flex justify-center py-16">
              <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <p className="py-8 text-center text-destructive">{error}</p>
          ) : posts.length === 0 ? (
            <p className="py-16 text-center text-muted-foreground">暂无帖子</p>
          ) : (
            posts.map((post) => (
              <PostCard
                key={post.id}
                post={post}
                canFavorite={!!currentUserId}
                onFavoriteToggle={handleFavoriteToggle}
              />
            ))
          )}
        </div>
      </div>

      <CreatePostDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        defaultSubjectCategory={subjectCategory || undefined}
        onCreated={loadPosts}
      />
    </div>
  );
}
