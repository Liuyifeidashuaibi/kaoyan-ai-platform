"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { ChatInput, type ChatSendPayload } from "@/components/chat/chat-input";
import { ChatMessageList } from "@/components/chat/chat-message-list";
import { ChatSidebar } from "@/components/chat/chat-sidebar";
import {
  ChatSidebarCollapsedRail,
  ChatSidebarMobileHeader,
} from "@/components/chat/chat-sidebar-chrome";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  createChatSession,
  deleteChatSession,
  getChatMessages,
  listChatSessions,
  streamChatMessage,
} from "@/lib/api/chat";
import type { ChatMessage, ChatSession } from "@/lib/api/types";
import { initApiBaseUrl } from "@/lib/config/api";
import { cn } from "@/lib/utils";

const SIDEBAR_COLLAPSED_KEY = "chat-sidebar-collapsed";

function syncChatSessionUrl(sessionId: string | null) {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (sessionId) {
    url.searchParams.set("session", sessionId);
  } else {
    url.searchParams.delete("session");
    url.searchParams.delete("autoReply");
  }
  const next = `${url.pathname}${url.search}${url.hash}`;
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (current !== next) {
    window.history.replaceState(null, "", next);
  }
}

export function ChatApp() {
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const autoReplyTriggeredRef = useRef<string | null>(null);
  const isStreamingRef = useRef(false);
  const skipNextMessageLoadRef = useRef(false);
  const loadGenerationRef = useRef(0);
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    void initApiBaseUrl();
  }, []);

  useEffect(() => {
    const stored = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
    if (stored === "false") {
      const t = window.setTimeout(() => setSidebarCollapsed(false), 0);
      return () => window.clearTimeout(t);
    }
  }, []);

  const collapseSidebar = useCallback(() => {
    setSidebarCollapsed(true);
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, "true");
    setSidebarOpen(false);
  }, []);

  const expandSidebar = useCallback(() => {
    setSidebarCollapsed(false);
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, "false");
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
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load sessions");
      } finally {
        if (!cancelled) setLoadingSessions(false);
      }
    })();
    return () => { cancelled = true; };
  }, [searchKeyword]);

  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }
    if (skipNextMessageLoadRef.current) {
      skipNextMessageLoadRef.current = false;
      syncChatSessionUrl(activeSessionId);
      return;
    }

    const generation = ++loadGenerationRef.current;
    let cancelled = false;

    (async () => {
      setLoadingMessages(true);
      try {
        const data = await getChatMessages(activeSessionId);
        if (
          !cancelled &&
          generation === loadGenerationRef.current &&
          !isStreamingRef.current
        ) {
          setMessages(data);
        }
      } catch (e) {
        if (!cancelled && generation === loadGenerationRef.current) {
          setError(e instanceof Error ? e.message : "Failed to load messages");
        }
      } finally {
        if (!cancelled && generation === loadGenerationRef.current) {
          setLoadingMessages(false);
        }
      }
    })();

    syncChatSessionUrl(activeSessionId);

    return () => {
      cancelled = true;
    };
  }, [activeSessionId]);

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
        audioFile?: Blob | null;
        enableTts?: boolean;
        imagePath?: string | null;
        localPreview?: string | null;
        skipOptimisticUser?: boolean;
        skipUserSave?: boolean;
      }
    ) => {
      const imageFile = options?.imageFile ?? null;
      const audioFile = options?.audioFile ?? null;
      const enableTts = options?.enableTts ?? false;
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
          audioFile,
          imagePath,
          skipUserSave: options?.skipUserSave,
          enableTts,
          signal: controller.signal,
          onToken: (token) => {
            setStreamingContent((prev) => prev + token);
          },
          onDone: (payload) => {
            if (!payload.ttsAudioBase64) return;
            try {
              const src = `data:audio/wav;base64,${payload.ttsAudioBase64}`;
              if (ttsAudioRef.current) {
                ttsAudioRef.current.pause();
              }
              const audio = new Audio(src);
              ttsAudioRef.current = audio;
              void audio.play();
            } catch {
              /* ignore playback errors */
            }
          },
        });
        const data = await getChatMessages(sessionId);
        // 服务端已有 image_path，不再需要 blob URL
        if (localPreview) URL.revokeObjectURL(localPreview);
        setMessages(data);
        await refreshSessions();
      } catch (e) {
        if ((e as Error)?.name === "AbortError") return;
        setError(e instanceof Error ? e.message : "Failed to send");
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
    syncChatSessionUrl(activeSessionId);
    void streamAssistantReply(activeSessionId, lastUser.content, {
      imagePath: lastUser.image_path,
      skipOptimisticUser: true,
      skipUserSave: true,
    });
  }, [
    activeSessionId, autoReply, isStreaming,
    loadingMessages, messages, streamAssistantReply,
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
      setError(e instanceof Error ? e.message : "Failed to create session");
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
        syncChatSessionUrl(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete");
    }
  };

  const handleSend = async ({
    content,
    imageFile,
    previewUrl,
    audioFile,
    enableTts,
  }: ChatSendPayload) => {
    const sendPayload = {
      imageFile: imageFile ?? null,
      audioFile: audioFile ?? null,
      enableTts,
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
        setError(e instanceof Error ? e.message : "Failed to send");
      }
      return;
    }

    await streamAssistantReply(activeSessionId, content, sendPayload);
  };

  return (
    <TooltipProvider delay={400}>
      <div className="flex h-full overflow-hidden">
        {sidebarOpen && (
          <button
            type="button"
            className="fixed inset-0 z-40 bg-black/30 md:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close sidebar"
          />
        )}

        {sidebarCollapsed && (
          <ChatSidebarCollapsedRail
            onExpandSidebar={expandSidebar}
            onNewChat={handleNewChat}
          />
        )}

        <div
          className={cn(
            "fixed inset-y-12 left-0 z-50 shrink-0 overflow-hidden transition-[width,transform] duration-200 ease-in-out md:static md:inset-y-0 md:z-auto md:min-w-0",
            sidebarCollapsed ? "md:w-0 md:pointer-events-none" : "md:w-56",
            sidebarOpen
              ? "w-56 translate-x-0"
              : "w-56 -translate-x-full md:translate-x-0"
          )}
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
            onCloseSidebar={collapseSidebar}
          />
        </div>

        <div className="relative flex min-h-0 min-w-0 flex-1 flex-col">
          <ChatSidebarMobileHeader
            onToggleSidebar={() => setSidebarOpen((open) => !open)}
            title={
              sessions.find((s) => s.id === activeSessionId)?.title ?? "Chat"
            }
          />

        {error && (
          <div className="shrink-0 border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">
            {error}
            <button
              type="button"
              className="ml-2 underline"
              onClick={() => setError(null)}
            >
              Dismiss
            </button>
          </div>
        )}

        {loadingMessages && messages.length === 0 && !isStreaming ? (
          <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
            Loading messages…
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
          disabled={loadingMessages && messages.length === 0 && !isStreaming}
        />
        </div>
      </div>
    </TooltipProvider>
  );
}
