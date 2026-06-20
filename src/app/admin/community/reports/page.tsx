import type { Metadata } from "next";

import { ReportsListClient } from "@/components/admin/community/reports-list-client";

export const metadata: Metadata = { title: "举报管理" };

export default function AdminCommunityReportsPage() {
  return <ReportsListClient />;
}
