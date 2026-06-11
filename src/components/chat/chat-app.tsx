"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Menu, X } from "lucide-react";

import { ChatInput } from "@/components/chat/chat-input";
import { ChatMessageList } from "@/components/chat/chat-message-list";
import { ChatSidebar } from "@/components/chat/chat-sidebar";
import { Button } from "@/components/ui/button";
import {
  createChatSession,
  deleteChatSession,
  getChatMessages,
  listChatSessions,
  streamChatMessage,
  uploadChatImage,
} from "@/lib/api/chat";
import type { ChatMessage, ChatSession } from "@/lib/api/types";

export function ChatApp() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionFromUrl = searchParams.get("session");
  const autoReply = searchParams.get("autoReply") === "1";

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(
    sessionFromUrl
  );
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [searchKeyword, setSearchKeyword] = useState("");
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const autoReplyTriggeredRef = useRef<string | null>(null);

  /* ── URL sync ─────────────────────────────────────────── */
  useEffect(() => {
    if (!sessionFromUrl) return;
    const t = window.setTimeout(() => setActiveSessionId(sessionFromUrl), 0);
    return () => window.clearTimeout(t);
  }, [sessionFromUrl]);

  /* ── Load session list ───────────────────────────────── */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await listChatSessions(searchKeyword);
        if (!cancelled) setSessions(data);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "加载会话失败");
      } finally {
        if (!cancelled) setLoadingSessions(false);
      }
    })();
    return () => { cancelled = true; };
  }, [searchKeyword]);

  /* ── Load messages for active session ───────────────── */
  useEffect(() => {
    if (!activeSessionId) return;
    let cancelled = false;
    (async () => {
      setLoadingMessages(true);
      try {
        const data = await getChatMessages(activeSessionId);
        if (!cancelled) setMessages(data);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "加载消息失败");
      } finally {
        if (!cancelled) setLoadingMessages(false);
      }
    })();
    router.replace(`/chat?session=${activeSessionId}`, { scroll: false });
    return () => { cancelled = true; };
  }, [activeSessionId, router]);

  const refreshSessions = useCallback(async (keyword = searchKeyword) => {
    const data = await listChatSessions(keyword);
    setSessions(data);
  }, [searchKeyword]);

  /* ── Core streaming function ─────────────────────────── */
  const streamAssistantReply = useCallback(
    async (
      sessionId: string,
      content: string,
      imagePath?: string | null,
      options?: { skipOptimisticUser?: boolean; skipUserSave?: boolean }
    ) => {
      abortControllerRef.current?.abort();
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setError(null);
      setIsStreaming(true);
      setStreamingContent("");

      const tempUserMsg: ChatMessage = {
        id: Date.now(),
        role: "user",
        content,
        image_path: imagePath ?? null,
        created_at: new Date().toISOString(),
      };

      if (!options?.skipOptimisticUser) {
        setMessages((prev) => [...prev, tempUserMsg]);
      }

      try {
        await streamChatMessage({
          sessionId,
          content,
          imagePath,
          skipUserSave: options?.skipUserSave,
          signal: controller.signal,
          onToken: (token) => {
            setStreamingContent((prev) => prev + token);
          },
        });
        const data = await getChatMessages(sessionId);
        setMessages(data);
        await refreshSessions();
      } catch (e) {
        if ((e as Error)?.name === "AbortError") return; // stopped by user
        setError(e instanceof Error ? e.message : "发送失败");
        if (!options?.skipOptimisticUser) {
          setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
        }
      } finally {
        setIsStreaming(false);
        setStreamingContent("");
        abortControllerRef.current = null;
      }
    },
    [refreshSessions]
  );

  /* ── Stop generation ─────────────────────────────────── */
  const handleStop = useCallback(() => {
    abortControllerRef.current?.abort();
  }, []);

  /* ── Auto-reply from wrong-questions one-tap ─────────── */
  useEffect(() => {
    if (!autoReply || !activeSessionId || loadingMessages || isStreaming) return;
    if (messages.length === 0) return;
    if (autoReplyTriggeredRef.current === activeSessionId) return;

    const hasAssistant = messages.some((m) => m.role === "assistant");
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (hasAssistant || !lastUser) return;

    autoReplyTriggeredRef.current = activeSessionId;
    router.replace(`/chat?session=${activeSessionId}`, { scroll: false });
    void streamAssistantReply(
      activeSessionId,
      lastUser.content,
      lastUser.image_path,
      { skipOptimisticUser: true, skipUserSave: true }
    );
  }, [
    activeSessionId, autoReply, isStreaming,
    loadingMessages, messages, router, streamAssistantReply,
  ]);

  /* ── Regenerate last assistant message ───────────────── */
  const handleRegenerate = useCallback(
    async (_messageIndex: number) => {
      if (!activeSessionId) return;
      const lastUser = [...messages].reverse().find((m) => m.role === "user");
      if (!lastUser) return;

      setMessages((prev) => {
        const idx = [...prev].reverse().findIndex((m) => m.role === "assistant");
        if (idx === -1) return prev;
        const arr = [...prev];
        arr.splice(prev.length - 1 - idx, 1);
        return arr;
      });

      await streamAssistantReply(
        activeSessionId,
        lastUser.content,
        lastUser.image_path,
        { skipOptimisticUser: true, skipUserSave: true }
      );
    },
    [activeSessionId, messages, streamAssistantReply]
  );

  /* ── Session actions ─────────────────────────────────── */
  const handleNewChat = async () => {
    setError(null);
    try {
      const session = await createChatSession();
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
      setMessages([]);
      setSidebarOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建会话失败");
    }
  };

  const handleSelectSession = (id: string) => {
    setActiveSessionId(id);
    setSidebarOpen(false);
  };

  const handleDeleteSession = async (id: string) => {
    try {
      await deleteChatSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (activeSessionId === id) {
        setActiveSessionId(null);
        setMessages([]);
        router.replace("/chat", { scroll: false });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除失败");
    }
  };

  /* ── Send message ────────────────────────────────────── */
  const sendToSession = useCallback(
    async (sessionId: string, content: string, imagePath?: string | null) => {
      await streamAssistantReply(sessionId, content, imagePath);
    },
    [streamAssistantReply]
  );

  const handleSend = async (content: string, imagePath?: string | null) => {
    if (!activeSessionId) {
      try {
        const session = await createChatSession();
        setSessions((prev) => [session, ...prev]);
        setActiveSessionId(session.id);
        await sendToSession(session.id, content, imagePath);
      } catch (e) {
        setError(e instanceof Error ? e.message : "发送失败");
      }
      return;
    }
    await sendToSession(activeSessionId, content, imagePath);
  };

  /* ── Render ──────────────────────────────────────────── */
  return (
    <div className="flex h-full overflow-hidden">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/30 md:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-label="关闭侧边栏"
        />
      )}

      {/* Sidebar */}
      <div
        className={`fixed inset-y-14 left-0 z-50 w-72 transition-transform md:static md:inset-y-0 md:z-auto md:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <ChatSidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          searchKeyword={searchKeyword}
          onSearchChange={setSearchKeyword}
          onNewChat={handleNewChat}
          onSelectSession={handleSelectSession}
          onDeleteSession={handleDeleteSession}
          loading={loadingSessions}
        />
      </div>

      {/* Main chat area */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* Mobile top bar */}
        <div className="flex shrink-0 items-center gap-2 border-b border-border px-3 py-2 md:hidden">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            {sidebarOpen ? <X className="size-4" /> : <Menu className="size-4" />}
          </Button>
          <span className="truncate text-sm font-medium">
            {sessions.find((s) => s.id === activeSessionId)?.title ?? "AI 聊天"}
          </span>
        </div>

        {/* Error banner */}
        {error && (
          <div className="shrink-0 border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">
            {error}
            <button
              type="button"
              className="ml-2 underline"
              onClick={() => setError(null)}
            >
              关闭
            </button>
          </div>
        )}

        {/* Message list */}
        {loadingMessages ? (
          <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
            加载消息…
          </div>
        ) : (
          <ChatMessageList
            messages={messages}
            streamingContent={streamingContent}
            isStreaming={isStreaming}
            onRegenerate={handleRegenerate}
          />
        )}

        {/* Input bar */}
        <ChatInput
          onSend={handleSend}
          onStop={handleStop}
          isStreaming={isStreaming}
          onUploadImage={async (file) => {
            const { image_path } = await uploadChatImage(file);
            return image_path;
          }}
          disabled={loadingMessages}
        />
      </div>
    </div>
  );
}
