"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { FileText, Loader2, UserPlus, UserMinus } from "lucide-react";

import { PostCard } from "@/components/community/post-card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  followUser,
  getUserProfile,
  listPosts,
  toggleFavorite,
  unfollowUser,
  updateMyProfile,
  updatePost,
} from "@/lib/api/community";
import type { CommunityPost, CommunityUser } from "@/lib/api/types";
import { POST_TYPES, SUBJECT_CATEGORIES, type PostType } from "@/lib/community/constants";
import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";

type UserProfileClientProps = {
  userId: string;
};

export function UserProfileClient({ userId }: UserProfileClientProps) {
  const [profile, setProfile] = useState<CommunityUser | null>(null);
  const [posts, setPosts] = useState<CommunityPost[]>([]);
  const [postType, setPostType] = useState<PostType | "">("");
  const [loading, setLoading] = useState(true);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [editCategory, setEditCategory] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = await getUserProfile(userId);
      setProfile(p);
      setEditCategory(p.subject_category ?? "");
      const postData = await listPosts({
        author_id: p.id,
        post_type: postType || undefined,
      });
      setPosts(postData.items);
    } catch {
      setProfile(null);
      setPosts([]);
    } finally {
      setLoading(false);
    }
  }, [userId, postType]);

  useEffect(() => {
    if (isSupabaseConfigured()) {
      const supabase = createClient();
      void supabase.auth.getUser().then(({ data }) => {
        setCurrentUserId(data.user?.id ?? null);
      });
    }
    void load();
  }, [load]);

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

  async function handleToggleHidden(postId: string, hidden: boolean) {
    const updated = await updatePost(postId, { is_hidden: hidden });
    setPosts((prev) =>
      prev.map((p) => (p.id === postId ? updated : p))
    );
  }

  async function handleFollow() {
    if (!profile) return;
    try {
      if (profile.is_following) {
        await unfollowUser(profile.id);
      } else {
        await followUser(profile.id);
      }
      await load();
    } catch {
      /* ignore */
    }
  }

  async function handleSaveCategory() {
    try {
      await updateMyProfile({ subject_category: editCategory });
      await load();
    } catch {
      /* ignore */
    }
  }

  if (loading && !profile) {
    return (
      <div className="flex justify-center py-24">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!profile) {
    return <p className="p-8 text-center text-muted-foreground">User not found</p>;
  }

  const displayName = profile.display_id || profile.nickname || "User";
  const isSelf = profile.is_self;

  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <Avatar size="lg">
          <AvatarImage src={profile.avatar_url ?? undefined} />
          <AvatarFallback>{displayName.slice(0, 1).toUpperCase()}</AvatarFallback>
        </Avatar>
        <div className="flex-1 space-y-2">
          <h1 className="text-2xl font-semibold">{displayName}</h1>
          {profile.subject_category && (
            <Badge variant="secondary">{profile.subject_category}</Badge>
          )}
          <div className="flex gap-4 text-sm text-muted-foreground">
            <Link href={`/following?user=${profile.id}`} className="hover:underline">
              Following {profile.following_count ?? 0}
            </Link>
            <Link href={`/followers?user=${profile.id}`} className="hover:underline">
              Followers {profile.follower_count ?? 0}
            </Link>
          </div>
        </div>
        <div className="flex gap-2">
          {isSelf ? (
            <div className="flex items-center gap-2">
              <select
                className="h-9 rounded-md border px-2 text-sm"
                value={editCategory}
                onChange={(e) => setEditCategory(e.target.value)}
              >
                <option value="">No subject set</option>
                {SUBJECT_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <Button size="sm" variant="outline" onClick={handleSaveCategory}>
                Save Subject
              </Button>
            </div>
          ) : currentUserId ? (
            <Button size="sm" variant="outline" onClick={handleFollow}>
              {profile.is_following ? (
                <>
                  <UserMinus />
                  Unfollow
                </>
              ) : (
                <>
                  <UserPlus />
                  Follow
                </>
              )}
            </Button>
          ) : null}
        </div>
      </div>

      <section className="space-y-4">
        <h2 className="flex items-center gap-1.5 text-sm font-medium">
          <FileText className="size-4" />
          Posts ({posts.length})
        </h2>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant={postType === "" ? "default" : "outline"}
            onClick={() => setPostType("")}
          >
            All
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
        {isSelf && (
          <p className="text-sm text-muted-foreground">
            Posts are public by default. Hidden posts won&apos;t appear on your profile, but you can still manage them below.
          </p>
        )}
        <div className="space-y-3">
          {posts.length === 0 ? (
            <p className="py-12 text-center text-muted-foreground">No posts yet</p>
          ) : (
            posts.map((post) => (
              <PostCard
                key={post.id}
                post={post}
                canFavorite={!!currentUserId}
                onFavoriteToggle={handleFavoriteToggle}
                showHiddenControls={isSelf}
                onToggleHidden={isSelf ? handleToggleHidden : undefined}
              />
            ))
          )}
        </div>
      </section>
    </div>
  );
}
