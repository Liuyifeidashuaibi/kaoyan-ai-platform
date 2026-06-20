import type { Metadata } from "next";

import { MonitoringSectionClient } from "@/components/admin/monitoring/monitoring-section-client";

export const metadata: Metadata = { title: "Agent 状态" };

export default function AdminMonitoringAgentsPage() {
  return <MonitoringSectionClient section="agents" />;
}
