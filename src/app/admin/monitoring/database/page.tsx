import type { Metadata } from "next";

import { MonitoringSectionClient } from "@/components/admin/monitoring/monitoring-section-client";

export const metadata: Metadata = { title: "数据库状态" };

export default function AdminMonitoringDatabasePage() {
  return <MonitoringSectionClient section="database" />;
}
