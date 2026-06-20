import { adminFetch } from "@/lib/admin/api/client";

export type DashboardMetrics = {
  usersTotal: number;
  postsTotal: number;
  schoolsTotal: number;
  majorsTotal: number;
  usersToday: number;
  postsToday: number;
};

export type ActivityItem = {
  id: string;
  type: "user" | "post" | "agent" | "sync" | "report";
  message: string;
  time: string;
  href?: string;
};

export async function fetchDashboardMetrics() {
  return adminFetch<DashboardMetrics>("/api/admin/dashboard/metrics");
}

export async function fetchDashboardActivity(limit = 10) {
  return adminFetch<ActivityItem[]>(`/api/admin/dashboard/activity?limit=${limit}`);
}
