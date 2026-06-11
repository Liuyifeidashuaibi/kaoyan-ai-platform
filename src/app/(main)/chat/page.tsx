import { Suspense } from "react";

import { ChatApp } from "@/components/chat/chat-app";
import { requireAuth } from "@/lib/auth/require-auth";

export default async function ChatPage() {
  await requireAuth("/chat");

  return (
    <Suspense
      fallback={
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          加载聊天...
        </div>
      }
    >
      <ChatApp />
    </Suspense>
  );
}
