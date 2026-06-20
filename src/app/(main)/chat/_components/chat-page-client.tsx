"use client";

import dynamic from "next/dynamic";

const ChatApp = dynamic(
  () => import("@/components/chat/chat-app").then((mod) => mod.ChatApp),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Loading chat…
      </div>
    ),
  }
);

export function ChatPageClient() {
  return (
    <div className="h-full min-h-0">
      <ChatApp />
    </div>
  );
}
