"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Menu, X } from "lucide-react";

import { ChatInput, type ChatSendPayload } from "@/components/chat/chat-input";
import { ChatMessageList } from "@/components/chat/chat-message-list";
import { ChatSidebar } from "@/components/chat/chat-sidebar";
import { Button } from "@/components/ui/button";
import {
  createChatSession,
  deleteChatSession,
  getChatMessages,
  listChatSessions,
  streamChatMessage,
} from "@/lib/api/chat";
import type { ChatMessage, ChatSession } from "@/lib/api/types";
import { initApiBaseUrl } from "@/lib/config/api";


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
  const isStreamingRef = useRef(false);
  const skipNextMessageLoadRef = useRef(false);

  useEffect(() => {
    void initApiBaseUrl();
  }, []);

  useEffect(() => {
    isStreamingRef.current = isStreaming;
  }, [isStreaming]);

  useEffect(() => {
    if (!sessionFromUrl) return;
    const t = window.setTimeout(() => setActiveSessionId(sessionFromUrl), 0);
    return () => window.clearTimeout(t);
  }, [sessionFromUrl]);

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

  useEffect(() => {
    if (!activeSessionId) return;
    if (skipNextMessageLoadRef.current) {
      skipNextMessageLoadRef.current = false;
      return;
    }

    let cancelled = false;
    (async () => {
      setLoadingMessages(true);
      try {
        const data = await getChatMessages(activeSessionId);
        if (!cancelled && !isStreamingRef.current) {
          setMessages(data);
        }
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

  const streamAssistantReply = useCallback(
    async (
      sessionId: string,
      content: string,
      options?: {
        imageFile?: File | null;
        imagePath?: string | null;
        localPreview?: string | null;
        skipOptimisticUser?: boolean;
        skipUserSave?: boolean;
      }
    ) => {
      const imageFile = options?.imageFile ?? null;
      const imagePath = options?.imagePath ?? null;
      const localPreview = options?.localPreview ?? null;

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
        local_preview: localPreview,
        created_at: new Date().toISOString(),
      };

      if (!options?.skipOptimisticUser) {
        setMessages((prev) => [...prev, tempUserMsg]);
      }

      try {
        await streamChatMessage({
          sessionId,
          content,
          imageFile,
          imagePath,
          skipUserSave: options?.skipUserSave,
          signal: controller.signal,
          onToken: (token) => {
            setStreamingContent((prev) => prev + token);
          },
        });
        const data = await getChatMessages(sessionId);
        // 服务端已有 image_path，不再需要 blob URL
        if (localPreview) URL.revokeObjectURL(localPreview);
        setMessages(data);
        await refreshSessions();
      } catch (e) {
        if ((e as Error)?.name === "AbortError") return;
        setError(e instanceof Error ? e.message : "发送失败");
        if (!options?.skipOptimisticUser) {
          setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
        }
        if (localPreview) URL.revokeObjectURL(localPreview);
      } finally {
        setIsStreaming(false);
        setStreamingContent("");
        abortControllerRef.current = null;
      }
    },
    [refreshSessions]
  );

  const handleStop = useCallback(() => {
    abortControllerRef.current?.abort();
  }, []);

  useEffect(() => {
    if (!autoReply || !activeSessionId || loadingMessages || isStreaming) return;
    if (messages.length === 0) return;
    if (autoReplyTriggeredRef.current === activeSessionId) return;

    const hasAssistant = messages.some((m) => m.role === "assistant");
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (hasAssistant || !lastUser) return;

    autoReplyTriggeredRef.current = activeSessionId;
    router.replace(`/chat?session=${activeSessionId}`, { scroll: false });
    void streamAssistantReply(activeSessionId, lastUser.content, {
      imagePath: lastUser.image_path,
      skipOptimisticUser: true,
      skipUserSave: true,
    });
  }, [
    activeSessionId, autoReply, isStreaming,
    loadingMessages, messages, router, streamAssistantReply,
  ]);

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

      await streamAssistantReply(activeSessionId, lastUser.content, {
        imagePath: lastUser.image_path,
        localPreview: lastUser.local_preview,
        skipOptimisticUser: true,
        skipUserSave: true,
      });
    },
    [activeSessionId, messages, streamAssistantReply]
  );

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

  const handleSend = async ({ content, imageFile, previewUrl }: ChatSendPayload) => {
    const sendPayload = {
      imageFile: imageFile ?? null,
      localPreview: previewUrl,
    };

    if (!activeSessionId) {
      try {
        const session = await createChatSession();
        setSessions((prev) => [session, ...prev]);
        skipNextMessageLoadRef.current = true;
        setActiveSessionId(session.id);
        setMessages([]);
        await streamAssistantReply(session.id, content, sendPayload);
      } catch (e) {
        setError(e instanceof Error ? e.message : "发送失败");
      }
      return;
    }

    await streamAssistantReply(activeSessionId, content, sendPayload);
  };

  return (
    <div className="flex h-full overflow-hidden">
      {sidebarOpen && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/30 md:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-label="关闭侧边栏"
        />
      )}

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

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
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

        <ChatInput
          onSend={handleSend}
          onStop={handleStop}
          isStreaming={isStreaming}
          disabled={loadingMessages}
        />
      </div>
    </div>
  );
}
