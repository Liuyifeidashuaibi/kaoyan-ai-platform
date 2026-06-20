import type { Metadata } from "next";

import { UserDetailClient } from "@/components/admin/users/user-detail-client";

export const metadata: Metadata = { title: "用户详情" };

export default async function AdminUserDetailPage({
  params,
}: {
  params: Promise<{ userId: string }>;
}) {
  const { userId } = await params;
  return <UserDetailClient userId={userId} />;
}
