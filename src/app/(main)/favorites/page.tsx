import { FavoritesClient } from "@/components/community/favorites-client";
import { requireAuth } from "@/lib/auth/require-auth";

export default async function FavoritesPage() {
  await requireAuth("/favorites");
  return <FavoritesClient />;
}
