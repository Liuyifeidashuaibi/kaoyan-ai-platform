import { requireAuth } from "@/lib/auth/require-auth";
import { AgentTemplatesClient } from "../_components/agent-templates-client";

export default async function AgentTemplatesPage() {
  await requireAuth("/agent/templates");
  return <AgentTemplatesClient />;
}
