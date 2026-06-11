"use client";

import Link from "next/link";
import {
  BookOpen,
  MessageSquarePlus,
  Search,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
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
}: ChatSidebarProps) {
  return (
    <aside className="flex h-full w-full flex-col border-r border-border bg-sidebar md:w-64 lg:w-72">
      <div className="flex flex-col gap-2 border-b border-border p-3">
        <Button onClick={onNewChat} className="w-full justify-start gap-2">
          <MessageSquarePlus className="size-4" />
          新建聊天
        </Button>

        <Link href="/wrong-questions">
          <Button variant="outline" className="w-full justify-start gap-2">
            <BookOpen className="size-4" />
            错题本
          </Button>
        </Link>

        <div className="relative">
          <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="搜索历史..."
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
              加载中...
            </p>
          )}
          {!loading && sessions.length === 0 && (
            <p className="px-2 py-4 text-center text-xs text-muted-foreground">
              暂无聊天记录
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
                aria-label="删除会话"
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
