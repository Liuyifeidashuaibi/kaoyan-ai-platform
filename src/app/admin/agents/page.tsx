import type { Metadata } from "next";

import { AgentControlCenter } from "@/components/admin/agents/agent-control-center";

export const metadata: Metadata = { title: "Agent 中心" };

export default function AdminAgentsPage() {
  return <AgentControlCenter />;
}
