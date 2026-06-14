"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, FileText, Loader2, UserPlus, UserMinus } from "lucide-react";

import { PostCard } from "@/components/community/post-card";
import { MaterialTimelineItem } from "@/components/wrong-questions/question-card";
import { QuestionDetailDialog } from "@/components/wrong-questions/question-detail-dialog";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  followUser,
  getUserProfile,
  listPosts,
  toggleFavorite,
  unfollowUser,
  updateMyProfile,
  updatePost,
} from "@/lib/api/community";
import { listPublicMaterials } from "@/lib/api/wrong-questions";
import type { CommunityPost, CommunityUser, WrongQuestion } from "@/lib/api/types";
import { POST_TYPES, SUBJECT_CATEGORIES, type PostType } from "@/lib/community/constants";
import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";

type UserProfileClientProps = {
  userId: string;
};

export function UserProfileClient({ userId }: UserProfileClientProps) {
  const [profile, setProfile] = useState<CommunityUser | null>(null);
  const [posts, setPosts] = useState<CommunityPost[]>([]);
  const [publicMaterials, setPublicMaterials] = useState<WrongQuestion[]>([]);
  const [postType, setPostType] = useState<PostType | "">("");
  const [loading, setLoading] = useState(true);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [editCategory, setEditCategory] = useState("");
  const [selectedMaterial, setSelectedMaterial] = useState<WrongQuestion | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = await getUserProfile(userId);
      setProfile(p);
      setEditCategory(p.subject_category ?? "");
      const [postData, materialData] = await Promise.all([
        listPosts({
          author_id: p.id,
          post_type: postType || undefined,
        }),
        listPublicMaterials(p.id),
      ]);
      setPosts(postData.items);
      setPublicMaterials(materialData);
    } catch {
      setProfile(null);
      setPosts([]);
      setPublicMaterials([]);
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
    return <p className="p-8 text-center text-muted-foreground">用户不存在</p>;
  }

  const displayName = profile.display_id || profile.nickname || "用户";
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
              关注 {profile.following_count ?? 0}
            </Link>
            <Link href={`/followers?user=${profile.id}`} className="hover:underline">
              粉丝 {profile.follower_count ?? 0}
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
                <option value="">未设置专业</option>
                {SUBJECT_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <Button size="sm" variant="outline" onClick={handleSaveCategory}>
                保存专业
              </Button>
            </div>
          ) : currentUserId ? (
            <Button size="sm" variant="outline" onClick={handleFollow}>
              {profile.is_following ? (
                <>
                  <UserMinus />
                  取消关注
                </>
              ) : (
                <>
                  <UserPlus />
                  关注
                </>
              )}
            </Button>
          ) : null}
        </div>
      </div>

      <Tabs defaultValue="posts">
        <TabsList>
          <TabsTrigger value="posts" className="gap-1.5">
            <FileText className="size-4" />
            帖子 ({posts.length})
          </TabsTrigger>
          <TabsTrigger value="materials" className="gap-1.5">
            <BookOpen className="size-4" />
            公开资料 ({publicMaterials.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="posts" className="mt-4 space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant={postType === "" ? "default" : "outline"}
              onClick={() => setPostType("")}
            >
              全部
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
              帖子默认公开；隐藏后他人无法在主页看到，你仍可在下方管理。
            </p>
          )}
          <div className="space-y-3">
            {posts.length === 0 ? (
              <p className="py-12 text-center text-muted-foreground">暂无帖子</p>
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
        </TabsContent>

        <TabsContent value="materials" className="mt-4 space-y-4">
          {isSelf && (
            <p className="text-sm text-muted-foreground">
              在
              <Link href="/wrong-questions" className="mx-1 underline">
                错题本
              </Link>
              中将资料设为「公开」后，会展示在这里供他人查看。
            </p>
          )}
          <div className="space-y-1">
            {publicMaterials.length === 0 ? (
              <p className="py-12 text-center text-muted-foreground">
                {isSelf ? "还没有公开的资料" : "该用户暂无公开资料"}
              </p>
            ) : (
              publicMaterials.map((item, index) => (
                <MaterialTimelineItem
                  key={item.id}
                  question={item}
                  isLast={index === publicMaterials.length - 1}
                  onClick={() => setSelectedMaterial(item)}
                />
              ))
            )}
          </div>
        </TabsContent>
      </Tabs>

      <QuestionDetailDialog
        question={selectedMaterial}
        open={!!selectedMaterial}
        onOpenChange={(open) => {
          if (!open) setSelectedMaterial(null);
        }}
        onAnalyze={async () => {}}
        onStartChat={async () => ""}
        onUpdateNotes={async () => {}}
        readOnly
      />
    </div>
  );
}
