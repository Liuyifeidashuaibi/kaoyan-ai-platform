import type { Metadata } from "next";

import { PostsListClient } from "@/components/admin/community/posts-list-client";

export const metadata: Metadata = { title: "帖子管理" };

export default function AdminCommunityPostsPage() {
  return <PostsListClient />;
}
