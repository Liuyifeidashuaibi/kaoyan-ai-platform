import type { Metadata } from "next";

import { PostStatsListClient } from "@/components/admin/users/post-stats-list-client";

export const metadata: Metadata = { title: "发帖统计" };

export default function AdminUsersPostsPage() {
  return <PostStatsListClient />;
}
