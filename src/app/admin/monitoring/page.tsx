import type { Metadata } from "next";

import { MonitoringOverviewClient } from "@/components/admin/monitoring/monitoring-overview-client";

export const metadata: Metadata = { title: "系统监控" };

export default function AdminMonitoringPage() {
  return <MonitoringOverviewClient />;
}
