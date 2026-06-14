"use client";

import dynamic from "next/dynamic";
import { use } from "react";

const PostDetailPage = dynamic(
  () =>
    import("@/components/community/post-detail-page").then(
      (mod) => mod.PostDetailPage
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex justify-center p-16 text-muted-foreground">加载帖子…</div>
    ),
  }
);

type PageProps = {
  params: Promise<{ postId: string }>;
};

export default function CommunityPostPage({ params }: PageProps) {
  const { postId } = use(params);
  return <PostDetailPage postId={postId} />;
}
