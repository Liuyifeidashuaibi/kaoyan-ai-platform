import { Suspense } from "react";

import { FollowingContent } from "@/components/community/following-content";
import { requireAuth } from "@/lib/auth/require-auth";

export default async function FollowingPage() {
  await requireAuth("/following");

  return (
    <Suspense fallback={<div className="p-8">加载中…</div>}>
      <FollowingContent />
    </Suspense>
  );
}
