import type { Metadata } from "next";

import { MonitoringSectionClient } from "@/components/admin/monitoring/monitoring-section-client";

export const metadata: Metadata = { title: "API 状态" };

export default function AdminMonitoringApiPage() {
  return <MonitoringSectionClient section="api" />;
}
