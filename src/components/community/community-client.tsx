"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, Plus, Search, Star, Users } from "lucide-react";

import { CommunityFeedSkeleton } from "@/components/community/community-feed-skeleton";
import { CreatePostDialog } from "@/components/community/create-post-dialog";
import { PostCard } from "@/components/community/post-card";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { listPosts, searchCommunity, toggleFavorite } from "@/lib/api/community";
import type { CommunityPost } from "@/lib/api/types";
import {
  COMMUNITY_FAVORITES_LABEL,
  COMMUNITY_SORT_TABS,
  POST_TYPES,
  communityFavoritesHref,
  type PostType,
} from "@/lib/community/constants";
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
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [page, setPage] = useState(1);
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

  const loadPosts = useCallback(async (pageNum = 1, append = false) => {
    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
      setError(null);
    }
    try {
      const data = await listPosts({
        sort,
        page: pageNum,
        post_type: postType || undefined,
        subject_category: subjectCategory || undefined,
        q: search.trim() || undefined,
      });
      setPosts((prev) => (append ? [...prev, ...data.items] : data.items));
      setPage(pageNum);
      setHasMore(data.has_more);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load";
      setError(
        msg.includes("Supabase")
          ? "Community service unavailable. Check that the backend is running."
          : msg
      );
      if (!append) setPosts([]);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [sort, postType, subjectCategory, search]);

  useEffect(() => {
    void loadPosts(1);
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
      void loadPosts(1);
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
        setHasMore(false);
        setPage(1);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Community</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/following" className={buttonVariants({ variant: "outline", size: "sm" })}>
            <Users />
            Following
          </Link>
          <Link
            href={communityFavoritesHref()}
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            <Star />
            {COMMUNITY_FAVORITES_LABEL}
          </Link>
          {mounted && currentUserId ? (
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus />
              New Post
            </Button>
          ) : mounted ? (
            <Link
              href="/login?next=/community"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              Sign in to post
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
            placeholder="Search user ID, subject area, or posts…"
            className="pl-9"
          />
        </div>
        <Button type="submit" variant="secondary">
          Search
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
              All Types
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
            Subject filter: {subjectCategory}
            <button
              type="button"
              className="ml-2 underline"
              onClick={() => {
                setSubjectCategory("");
                router.replace("/community");
              }}
            >
              Clear
            </button>
          </p>
        )}

        <div className="space-y-3">
          {loading ? (
            <CommunityFeedSkeleton count={5} />
          ) : error ? (
            <p className="py-8 text-center text-destructive">{error}</p>
          ) : posts.length === 0 ? (
            <p className="py-16 text-center text-muted-foreground">No posts yet</p>
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
                    onClick={() => void loadPosts(page + 1, true)}
                    disabled={loadingMore}
                  >
                    {loadingMore ? (
                      <>
                        <Loader2 className="animate-spin" />
                        Loading…
                      </>
                    ) : (
                      "Load more"
                    )}
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <CreatePostDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        defaultSubjectCategory={subjectCategory || undefined}
        onCreated={() => void loadPosts(1)}
      />
    </div>
  );
}
