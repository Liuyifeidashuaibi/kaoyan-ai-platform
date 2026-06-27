import { requireAuth } from "@/lib/auth/require-auth";
import { AgentWorkbenchClient } from "./_components/agent-workbench-client";

export default async function AgentWorkbenchPage() {
  await requireAuth("/agent");
  return <AgentWorkbenchClient />;
}
