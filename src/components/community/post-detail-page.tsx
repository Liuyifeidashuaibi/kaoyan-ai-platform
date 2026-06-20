"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Eye,
  EyeOff,
  Loader2,
  MessageCircle,
  Star,
  Trash2,
} from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import {
  createComment,
  deletePost,
  getPost,
  listComments,
  toggleFavorite,
  updatePost,
} from "@/lib/api/community";
import type { CommunityComment, CommunityPost } from "@/lib/api/types";
import {
  COMMUNITY_FAVORITES_LABEL,
  POST_TYPE_LABELS,
  communityFavoritesHref,
} from "@/lib/community/constants";
import {
  attachmentPreviewUrl,
  getImageAttachments,
} from "@/lib/community/post-utils";
import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";

type PostDetailPageProps = {
  postId: string;
};

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function PostDetailPage({ postId }: PostDetailPageProps) {
  const router = useRouter();
  const [post, setPost] = useState<CommunityPost | null>(null);
  const [comments, setComments] = useState<CommunityComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [reply, setReply] = useState("");
  const [replyTo, setReplyTo] = useState<CommunityComment | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [favoriteMsg, setFavoriteMsg] = useState<string | null>(null);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);

  useEffect(() => {
    if (!isSupabaseConfigured()) return;
    const supabase = createClient();
    void supabase.auth.getUser().then(({ data }) => {
      setCurrentUserId(data.user?.id ?? null);
    });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, c] = await Promise.all([getPost(postId), listComments(postId)]);
      setPost(p);
      setComments(c);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
      setPost(null);
    } finally {
      setLoading(false);
    }
  }, [postId]);

  useEffect(() => {
    void load();
  }, [load]);

  const isAuthor = post && currentUserId && post.author_id === currentUserId;

  const topLevel = useMemo(
    () => comments.filter((c) => !c.parent_id),
    [comments]
  );

  const repliesByParent = useMemo(() => {
    const map = new Map<string, CommunityComment[]>();
    for (const c of comments) {
      if (!c.parent_id) continue;
      const list = map.get(c.parent_id) ?? [];
      list.push(c);
      map.set(c.parent_id, list);
    }
    return map;
  }, [comments]);

  const imageAttachments = useMemo(
    () => (post ? getImageAttachments(post.attachments) : []),
    [post]
  );

  const otherAttachments = useMemo(() => {
    if (!post) return [];
    const imageUrls = new Set(getImageAttachments(post.attachments).map((a) => a.url));
    return post.attachments.filter((a) => !imageUrls.has(a.url));
  }, [post]);

  async function handleComment() {
    if (!reply.trim()) return;
    setSubmitting(true);
    try {
      await createComment(postId, reply.trim(), replyTo?.id);
      setReply("");
      setReplyTo(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to comment");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleFavorite() {
    setFavoriteMsg(null);
    try {
      const result = await toggleFavorite(postId);
      setPost((prev) =>
        prev
          ? {
              ...prev,
              is_favorited: result.favorited,
              favorite_count: prev.favorite_count + (result.favorited ? 1 : -1),
            }
          : prev
      );
      if (result.favorited) {
        setFavoriteMsg(`Saved to ${COMMUNITY_FAVORITES_LABEL}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    }
  }

  async function handleToggleHidden() {
    if (!post) return;
    try {
      const updated = await updatePost(post.id, { is_hidden: !post.is_hidden });
      setPost(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    }
  }

  async function handleDelete() {
    if (!confirm("Delete this post?")) return;
    try {
      await deletePost(postId);
      router.push("/community");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete");
    }
  }

  function renderComment(c: CommunityComment, depth = 0) {
    const name = c.author.display_id || c.author.nickname || "User";
    const children = repliesByParent.get(c.id) ?? [];
    return (
      <div key={c.id} className={depth > 0 ? "ml-6 border-l pl-3" : ""}>
        <div className="flex gap-2 py-2">
          <Avatar size="sm">
            <AvatarImage src={c.author.avatar_url ?? undefined} />
            <AvatarFallback>{name.slice(0, 1)}</AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Link
                href={`/user/${c.author.display_id || c.author.id}`}
                className="font-medium text-foreground hover:underline"
              >
                {name}
              </Link>
              <span>{formatTime(c.created_at)}</span>
            </div>
            <p className="mt-1 text-sm whitespace-pre-wrap">{c.content}</p>
            {currentUserId && (
              <button
                type="button"
                className="mt-1 text-xs text-muted-foreground hover:text-foreground"
                onClick={() => setReplyTo(c)}
              >
                Reply
              </button>
            )}
          </div>
        </div>
        {children.map((child) => renderComment(child, depth + 1))}
      </div>
    );
  }

  if (loading && !post) {
    return (
      <div className="flex justify-center py-24">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!post) {
    return (
      <div className="flex flex-col items-center gap-4 p-8">
        <p className="text-muted-foreground">{error || "Post not found"}</p>
        <Button variant="outline" onClick={() => router.push("/community")}>
          Back to Community
        </Button>
      </div>
    );
  }

  const authorName = post.author.display_id || post.author.nickname || "User";

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-8 lg:px-10 xl:max-w-[1200px]">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon-sm" onClick={() => router.back()}>
          <ArrowLeft />
        </Button>
        <Link href="/community" className="text-sm text-muted-foreground hover:underline">
          Community
        </Link>
      </div>

      <header className="space-y-4 border-b pb-6">
        <h1 className="text-3xl font-semibold leading-tight tracking-tight lg:text-4xl">
          {post.title}
        </h1>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">{POST_TYPE_LABELS[post.post_type]}</Badge>
          <Badge variant="secondary">{post.subject_category}</Badge>
          {post.grade && <Badge variant="outline">{post.grade}</Badge>}
          {post.university_name && (
            <Badge variant="outline">{post.university_name}</Badge>
          )}
          {post.is_hidden && isAuthor && (
            <Badge variant="secondary">Hidden (only you)</Badge>
          )}
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Avatar size="sm">
            <AvatarImage src={post.author.avatar_url ?? undefined} />
            <AvatarFallback>{authorName.slice(0, 1).toUpperCase()}</AvatarFallback>
          </Avatar>
          <Link
            href={`/user/${post.author.display_id || post.author.id}`}
            className="font-medium hover:underline"
          >
            {authorName}
          </Link>
          {post.author.subject_category && (
            <Badge variant="outline" className="text-xs">
              {post.author.subject_category}
            </Badge>
          )}
          <span className="text-muted-foreground">{formatTime(post.created_at)}</span>
        </div>
      </header>

      <article className="space-y-6">
        <p className="text-base leading-7 whitespace-pre-wrap lg:text-[17px] lg:leading-8">
          {post.content}
        </p>

        {imageAttachments.length > 0 && (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
            {imageAttachments.map((a) => (
              <a
                key={a.url}
                href={attachmentPreviewUrl(a)}
                target="_blank"
                rel="noreferrer"
                className="overflow-hidden rounded-lg border bg-muted/30"
              >
                <img
                  src={attachmentPreviewUrl(a)}
                  alt={a.name || "Image attachment"}
                  className="aspect-[4/3] w-full object-cover lg:max-h-72"
                />
              </a>
            ))}
          </div>
        )}

        {otherAttachments.length > 0 && (
          <div className="space-y-2">
            {otherAttachments.map((a) => (
              <a
                key={a.url}
                href={attachmentPreviewUrl(a)}
                target="_blank"
                rel="noreferrer"
                className="block text-sm text-primary hover:underline"
              >
                {a.name || "View attachment"}
              </a>
            ))}
          </div>
        )}
      </article>

      <div className="flex flex-wrap items-center gap-2">
        {currentUserId && (
          <Button
            variant={post.is_favorited ? "default" : "outline"}
            size="sm"
            onClick={handleFavorite}
          >
            <Star className={post.is_favorited ? "fill-current" : ""} />
            {post.is_favorited ? "Saved" : "Save"}
            <span className="text-muted-foreground">({post.favorite_count})</span>
          </Button>
        )}
        {isAuthor && (
          <>
            <Button variant="outline" size="sm" onClick={handleToggleHidden}>
              {post.is_hidden ? <Eye /> : <EyeOff />}
              {post.is_hidden ? "Unhide" : "Hide"}
            </Button>
            <Button variant="outline" size="sm" onClick={handleDelete}>
              <Trash2 />
              Delete
            </Button>
          </>
        )}
      </div>

      {favoriteMsg && (
        <p className="text-sm text-primary">
          {favoriteMsg}{" "}
          <Link href={communityFavoritesHref()} className="underline">
            View {COMMUNITY_FAVORITES_LABEL}
          </Link>
        </p>
      )}

      <Separator />

      <section>
        <h2 className="mb-3 flex items-center gap-1 text-sm font-medium">
          <MessageCircle className="size-4" />
          Comments ({post.comment_count})
        </h2>
        <div className="space-y-1">
          {topLevel.length === 0 ? (
            <p className="py-4 text-sm text-muted-foreground">No comments yet. Be the first!</p>
          ) : (
            topLevel.map((c) => renderComment(c))
          )}
        </div>
      </section>

      {currentUserId ? (
        <div className="space-y-2">
          {replyTo && (
            <p className="text-xs text-muted-foreground">
              Replying to @{replyTo.author.display_id || replyTo.author.nickname}
              <button
                type="button"
                className="ml-2 underline"
                onClick={() => setReplyTo(null)}
              >
                Cancel
              </button>
            </p>
          )}
          <Textarea
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            placeholder="Write a comment…"
            rows={3}
          />
          <Button onClick={handleComment} disabled={submitting || !reply.trim()}>
            Send
          </Button>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          <Link href={`/login?next=/community/posts/${postId}`} className="underline">
            Sign in
          </Link>
          {" "}to comment
        </p>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
