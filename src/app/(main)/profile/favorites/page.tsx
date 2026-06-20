import { redirect } from "next/navigation";

import { communityFavoritesHref } from "@/lib/community/constants";

/** Profile entry point — same list as Community → Favorites */
export default function ProfileFavoritesPage() {
  redirect(communityFavoritesHref());
}
