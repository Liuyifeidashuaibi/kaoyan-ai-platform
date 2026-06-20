import type { Metadata } from "next";

import { MonitoringSectionClient } from "@/components/admin/monitoring/monitoring-section-client";

export const metadata: Metadata = { title: "任务队列" };

export default function AdminMonitoringQueuePage() {
  return <MonitoringSectionClient section="queue" />;
}
