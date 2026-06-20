import type { Metadata } from "next";

import { FavoritesListClient } from "@/components/admin/users/favorites-list-client";

export const metadata: Metadata = { title: "收藏统计" };

export default function AdminUsersFavoritesPage() {
  return <FavoritesListClient />;
}
