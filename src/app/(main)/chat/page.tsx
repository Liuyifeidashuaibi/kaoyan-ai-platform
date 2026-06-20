import { Suspense } from "react";

import { ChatPageClient } from "./_components/chat-page-client";
import { requireAuth } from "@/lib/auth/require-auth";

export default async function ChatPage() {
  await requireAuth("/chat");

  return (
    <Suspense
      fallback={
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          Loading chat…
        </div>
      }
    >
      <ChatPageClient />
    </Suspense>
  );
}
