import type { Metadata } from "next";

import { FollowsListClient } from "@/components/admin/users/follows-list-client";

export const metadata: Metadata = { title: "关注关系" };

export default function AdminUsersFollowsPage() {
  return <FollowsListClient />;
}
