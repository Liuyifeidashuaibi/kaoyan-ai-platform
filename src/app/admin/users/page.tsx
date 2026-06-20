import type { Metadata } from "next";

import { UsersListClient } from "@/components/admin/users/users-list-client";

export const metadata: Metadata = { title: "用户列表" };

export default function AdminUsersPage() {
  return <UsersListClient />;
}
