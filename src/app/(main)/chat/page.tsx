import { PagePlaceholder } from "@/components/layout/page-placeholder";
import { requireAuth } from "@/lib/auth/require-auth";

export default async function ChatPage() {
  await requireAuth("/chat");

  return (
    <PagePlaceholder
      title="AI 聊天"
      description="与 AI 助手对话，获取备考答疑、知识点讲解与学习规划建议。"
    />
  );
}
