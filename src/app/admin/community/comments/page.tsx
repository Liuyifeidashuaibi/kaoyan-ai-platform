import type { Metadata } from "next";

import { CommentsListClient } from "@/components/admin/community/comments-list-client";

export const metadata: Metadata = { title: "评论管理" };

export default function AdminCommunityCommentsPage() {
  return <CommentsListClient />;
}
