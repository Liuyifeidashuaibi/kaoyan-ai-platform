import type { Metadata } from "next";

import { MonitoringSectionClient } from "@/components/admin/monitoring/monitoring-section-client";

export const metadata: Metadata = { title: "错误日志" };

export default function AdminMonitoringErrorsPage() {
  return <MonitoringSectionClient section="errors" />;
}
