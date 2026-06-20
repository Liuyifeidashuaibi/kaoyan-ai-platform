import { adminFetch } from "@/lib/admin/api/client";

export type MonitoringHealth = {
  api: { status: string; latencyMs: number };
  database: { status: string; connected: boolean };
  agent: { status: string; activeTasks: number };
  queue: { pending: number };
  llmConfigured: boolean;
};

export async function fetchMonitoringHealth() {
  return adminFetch<MonitoringHealth>("/api/admin/monitoring/health");
}

export async function fetchMonitoringSection(section: string) {
  return adminFetch<Record<string, unknown>>(`/api/admin/monitoring/${section}`);
}
