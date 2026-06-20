"use client";

import {
  MessageSquarePlus,
  Search,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatSidebarOpenHeader } from "@/components/chat/chat-sidebar-chrome";
import type { ChatSession } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type ChatSidebarProps = {
  sessions: ChatSession[];
  activeSessionId: string | null;
  searchKeyword: string;
  onSearchChange: (value: string) => void;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  loading?: boolean;
  onCloseSidebar?: () => void;
};

export function ChatSidebar({
  sessions,
  activeSessionId,
  searchKeyword,
  onSearchChange,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  loading,
  onCloseSidebar,
}: ChatSidebarProps) {
  return (
    <aside className="flex h-full w-full min-w-0 flex-col border-r border-border bg-sidebar">
      {onCloseSidebar && (
        <ChatSidebarOpenHeader onCloseSidebar={onCloseSidebar} />
      )}

      <div className="space-y-2 border-b border-border p-2.5 pt-1">
        <Button onClick={onNewChat} className="w-full justify-start gap-2">
          <MessageSquarePlus className="size-4" />
          New Chat
        </Button>

        <div className="relative">
          <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search history..."
            value={searchKeyword}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-8"
          />
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="space-y-0.5 p-2">
          {loading && (
            <p className="px-2 py-4 text-center text-xs text-muted-foreground">
              Loading...
            </p>
          )}
          {!loading && sessions.length === 0 && (
            <p className="px-2 py-4 text-center text-xs text-muted-foreground">
              No chat history yet
            </p>
          )}
          {sessions.map((session) => (
            <div
              key={session.id}
              className={cn(
                "group flex items-center gap-1 rounded-lg pr-1",
                activeSessionId === session.id && "bg-sidebar-accent"
              )}
            >
              <button
                type="button"
                onClick={() => onSelectSession(session.id)}
                className={cn(
                  "flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition-colors",
                  activeSessionId === session.id
                    ? "text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent/60"
                )}
              >
                <MessageSquarePlus className="size-3.5 shrink-0 opacity-60" />
                <span className="truncate">{session.title}</span>
              </button>
              <Button
                variant="ghost"
                size="icon-xs"
                className="opacity-0 group-hover:opacity-100"
                onClick={() => onDeleteSession(session.id)}
                aria-label="Delete session"
              >
                <Trash2 className="size-3" />
              </Button>
            </div>
          ))}
        </div>
      </ScrollArea>
    </aside>
  );
}
