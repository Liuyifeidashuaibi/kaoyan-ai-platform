import type { Metadata } from "next";

import { ModerationListClient } from "@/components/admin/community/moderation-list-client";

export const metadata: Metadata = { title: "内容审核" };

export default function AdminCommunityModerationPage() {
  return <ModerationListClient />;
}
