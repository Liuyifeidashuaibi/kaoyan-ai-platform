"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Loader2, MessageCircle, Star } from "lucide-react";
import { useState } from "react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { CommunityPost } from "@/lib/api/types";
import { POST_TYPE_LABELS } from "@/lib/community/constants";
import {
  attachmentPreviewUrl,
  getImageAttachments,
  PREVIEW_IMAGE_COUNT,
  truncatePostContent,
} from "@/lib/community/post-utils";
import { cn } from "@/lib/utils";

type PostCardProps = {
  post: CommunityPost;
  className?: string;
  canFavorite?: boolean;
  onFavoriteToggle?: (postId: string) => Promise<void>;
  showHiddenControls?: boolean;
  onToggleHidden?: (postId: string, hidden: boolean) => Promise<void>;
};

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function PostCard({
  post,
  className,
  canFavorite = false,
  onFavoriteToggle,
  showHiddenControls = false,
  onToggleHidden,
}: PostCardProps) {
  const router = useRouter();
  const [favoriting, setFavoriting] = useState(false);
  const [hiding, setHiding] = useState(false);
  const authorName = post.author.display_id || post.author.nickname || "用户";
  const allImages = getImageAttachments(post.attachments);
  const previewImages = allImages.slice(0, PREVIEW_IMAGE_COUNT);
  const extraImageCount = Math.max(0, allImages.length - PREVIEW_IMAGE_COUNT);
  const hasContent = Boolean(post.content?.trim());

  return (
    <Card
      className={cn("cursor-pointer transition-colors hover:bg-muted/40", className)}
      onClick={() => router.push(`/community/posts/${post.id}`)}
    >
      <CardHeader className="flex flex-row items-start gap-3 space-y-0 pb-2">
        <Link
          href={`/user/${post.author.display_id || post.author.id}`}
          onClick={(e) => e.stopPropagation()}
        >
          <Avatar size="sm">
            <AvatarImage src={post.author.avatar_url ?? undefined} alt={authorName} />
            <AvatarFallback>{authorName.slice(0, 1).toUpperCase()}</AvatarFallback>
          </Avatar>
        </Link>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/user/${post.author.display_id || post.author.id}`}
              className="text-sm font-medium hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {authorName}
            </Link>
            {post.author.subject_category && (
              <Badge variant="secondary" className="text-xs">
                {post.author.subject_category}
              </Badge>
            )}
            <span className="text-xs text-muted-foreground">{formatTime(post.created_at)}</span>
          </div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <Badge variant="outline">{POST_TYPE_LABELS[post.post_type]}</Badge>
            <Badge variant="outline">{post.subject_category}</Badge>
            {post.grade && <Badge variant="outline">{post.grade}</Badge>}
            {post.university_name && (
              <Badge variant="secondary">{post.university_name}</Badge>
            )}
            {post.is_hidden && showHiddenControls && (
              <Badge variant="secondary">已隐藏</Badge>
            )}
          </div>
        </div>
        {showHiddenControls && onToggleHidden && (
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="shrink-0"
            disabled={hiding}
            title={post.is_hidden ? "取消隐藏" : "隐藏帖子"}
            onClick={async (e) => {
              e.stopPropagation();
              setHiding(true);
              try {
                await onToggleHidden(post.id, !post.is_hidden);
              } finally {
                setHiding(false);
              }
            }}
          >
            {hiding ? (
              <Loader2 className="size-4 animate-spin" />
            ) : post.is_hidden ? (
              <Eye className="size-4" />
            ) : (
              <EyeOff className="size-4" />
            )}
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        <h3 className="line-clamp-2 font-medium leading-snug">{post.title}</h3>
        {hasContent && (
          <p className="line-clamp-3 text-sm text-muted-foreground">
            {truncatePostContent(post.content, 120)}
          </p>
        )}

        {previewImages.length > 0 && (
          <div
            className={cn(
              "grid gap-1.5",
              previewImages.length === 1 && "grid-cols-1 max-w-xs",
              previewImages.length === 2 && "grid-cols-2",
              previewImages.length >= 3 && "grid-cols-3"
            )}
          >
            {previewImages.map((att, index) => {
              const isLast = index === previewImages.length - 1;
              const showMore = isLast && extraImageCount > 0;
              return (
                <div
                  key={att.url}
                  className="relative aspect-[4/3] overflow-hidden rounded-md border bg-muted/30"
                >
                  <img
                    src={attachmentPreviewUrl(att)}
                    alt={att.name || "图片预览"}
                    className="size-full object-cover"
                    loading="lazy"
                  />
                  {showMore && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/45 text-sm font-medium text-white">
                      +{extraImageCount}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          {canFavorite && onFavoriteToggle ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-auto gap-1 px-1 py-0 text-xs text-muted-foreground hover:text-foreground"
              disabled={favoriting}
              onClick={async (e) => {
                e.stopPropagation();
                setFavoriting(true);
                try {
                  await onFavoriteToggle(post.id);
                } finally {
                  setFavoriting(false);
                }
              }}
            >
              {favoriting ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Star
                  className={cn(
                    "size-3.5",
                    post.is_favorited && "fill-amber-400 text-amber-500"
                  )}
                />
              )}
              {post.favorite_count}
            </Button>
          ) : (
            <span className="inline-flex items-center gap-1">
              <Star className="size-3.5" />
              {post.favorite_count}
            </span>
          )}
          <span className="inline-flex items-center gap-1">
            <MessageCircle className="size-3.5" />
            {post.comment_count}
          </span>
          <span className="inline-flex items-center gap-1">
            <Eye className="size-3.5" />
            {post.view_count}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
