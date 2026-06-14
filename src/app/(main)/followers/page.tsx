import { Suspense } from "react";

import { FollowersContent } from "@/components/community/followers-content";
import { requireAuth } from "@/lib/auth/require-auth";

export default async function FollowersPage() {
  await requireAuth("/followers");

  return (
    <Suspense fallback={<div className="p-8">加载中…</div>}>
      <FollowersContent />
    </Suspense>
  );
}
