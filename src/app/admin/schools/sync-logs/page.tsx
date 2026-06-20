import type { Metadata } from "next";

import { SyncLogsClient } from "@/components/admin/schools/sync-logs-client";

export const metadata: Metadata = { title: "同步记录" };

export default function AdminSchoolsSyncLogsPage() {
  return <SyncLogsClient />;
}
