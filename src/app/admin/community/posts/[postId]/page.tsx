import type { Metadata } from "next";

import { PostDetailClient } from "@/components/admin/community/post-detail-client";

export const metadata: Metadata = { title: "帖子详情" };

export default async function AdminPostDetailPage({
  params,
}: {
  params: Promise<{ postId: string }>;
}) {
  const { postId } = await params;
  return <PostDetailClient postId={postId} />;
}
