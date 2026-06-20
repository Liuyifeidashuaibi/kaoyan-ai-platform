import { adminFetch } from "@/lib/admin/api/client";

export type AgentPlan = {
  planId: string;
  intent: string;
  steps: { order: number; title: string; duration: string }[];
  impact: string;
  risk: "low" | "medium" | "high";
  riskReason: string;
};

export type AgentTask = {
  id: string;
  title: string;
  status: string;
  statusLabel: string;
  agent: string;
  progress: number;
  plan?: AgentPlan;
  logs?: { time: string; message: string }[];
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
};

export type AgentStatusItem = {
  id: string;
  name: string;
  status: string;
  lastRun: string;
  successRate: string;
  taskCount: number;
};

export async function fetchAgentStatus() {
  return adminFetch<AgentStatusItem[]>("/api/admin/agents/status");
}

export async function fetchAgentTasks() {
  return adminFetch<AgentTask[]>("/api/admin/agents/tasks");
}

export async function createAgentPlan(intent: string) {
  return adminFetch<AgentPlan>("/api/admin/agents/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ intent }),
  });
}

export async function executeAgentPlan(planId: string) {
  return adminFetch<AgentTask>("/api/admin/agents/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan_id: planId }),
  });
}

export async function retryAgentTask(taskId: string) {
  return adminFetch<AgentTask>(`/api/admin/agents/tasks/${taskId}/retry`, {
    method: "POST",
  });
}

export async function cancelAgentTask(taskId: string) {
  return adminFetch<AgentTask>(`/api/admin/agents/tasks/${taskId}/cancel`, {
    method: "POST",
  });
}

export async function fetchAgentTask(taskId: string) {
  return adminFetch<AgentTask>(`/api/admin/agents/tasks/${taskId}`);
}
