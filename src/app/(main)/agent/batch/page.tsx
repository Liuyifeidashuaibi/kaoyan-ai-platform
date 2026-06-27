import { requireAuth } from "@/lib/auth/require-auth";
import { AgentBatchClient } from "../_components/agent-batch-client";

export default async function AgentBatchPage() {
  await requireAuth("/agent/batch");
  return <AgentBatchClient />;
}
