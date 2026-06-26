"use client";

import React, {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import dynamic from "next/dynamic";
import { Check, ChevronDown, Copy, RefreshCw, ThumbsDown, ThumbsUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ChatMessage } from "@/lib/api/types";
import { userMessageDisplayText } from "@/lib/chat/display";
import { resolveUploadUrl } from "@/lib/config/api";
import { cn } from "@/lib/utils";

const ChatMarkdownContent = dynamic(
  () =>
    import("@/components/chat/chat-markdown-content").then(
      (mod) => mod.ChatMarkdownContent
    ),
  {
    loading: () => (
      <div className="my-1 h-4 w-40 animate-pulse rounded bg-muted/80" />
    ),
  }
);

/* ── Types ───────────────────────────────────────────────── */
type MessageActionsProps = {
  content: string;
  onRegenerate?: () => void;
  showRegenerate?: boolean;
};

type MessageBubbleProps = {
  role: string;
  content: string;
  displayContent?: string | null;
  imagePath?: string | null;
  localPreview?: string | null;
  isStreaming?: boolean;
  onRegenerate?: () => void;
};

type ChatMessageListProps = {
  messages: ChatMessage[];
  streamingContent?: string;
  isStreaming?: boolean;
  onRegenerate?: (messageIndex: number) => void;
};

/* ── Copy button with checkmark ─────────────────────────── */
function CopyButton({ text, className }: { text: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [text]);

  return (
    <Button
      variant="ghost"
      size="icon-xs"
      onClick={handleCopy}
      className={cn("size-7 text-muted-foreground hover:text-foreground", className)}
      aria-label="Copy"
    >
      {copied ? <Check className="size-3.5 text-green-500" /> : <Copy className="size-3.5" />}
    </Button>
  );
}

/* ── Message actions toolbar ────────────────────────────── */
const MessageActions = memo(function MessageActions({
  content,
  onRegenerate,
  showRegenerate,
}: MessageActionsProps) {
  const [thumbState, setThumbState] = useState<"up" | "down" | null>(null);

  return (
    <div className="mt-1.5 flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
      <CopyButton text={content} />
      <Button
        variant="ghost"
        size="icon-xs"
        onClick={() => setThumbState(thumbState === "up" ? null : "up")}
        className={cn(
          "size-7 text-muted-foreground hover:text-foreground",
          thumbState === "up" && "text-green-500 hover:text-green-500"
        )}
        aria-label="Like"
      >
        <ThumbsUp className="size-3.5" />
      </Button>
      <Button
        variant="ghost"
        size="icon-xs"
        onClick={() => setThumbState(thumbState === "down" ? null : "down")}
        className={cn(
          "size-7 text-muted-foreground hover:text-foreground",
          thumbState === "down" && "text-red-500 hover:text-red-500"
        )}
        aria-label="Dislike"
      >
        <ThumbsDown className="size-3.5" />
      </Button>
      {showRegenerate && onRegenerate && (
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={onRegenerate}
          className="size-7 text-muted-foreground hover:text-foreground"
          aria-label="Regenerate"
        >
          <RefreshCw className="size-3.5" />
        </Button>
      )}
    </div>
  );
});

/* ── Typing cursor ───────────────────────────────────────── */
function TypingCursor() {
  return (
    <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-current align-middle" />
  );
}

/* ── Thinking dots ───────────────────────────────────────── */
function ThinkingDots() {
  return (
    <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
      <span className="inline-flex gap-1">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="size-1.5 animate-bounce rounded-full bg-muted-foreground"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </span>
      <span>Generating response…</span>
    </div>
  );
}

/* ── Single message bubble ───────────────────────────────── */
const MessageBubble = memo(function MessageBubble({
  role,
  content,
  displayContent,
  imagePath,
  localPreview,
  isStreaming,
  onRegenerate,
}: MessageBubbleProps) {
  const isUser = role === "user";
  const imageSrc = localPreview || (imagePath ? resolveUploadUrl(imagePath) : "");
  const userText = isUser ? userMessageDisplayText(content, displayContent) : content;
  const [imageBroken, setImageBroken] = useState(false);

  useEffect(() => {
    setImageBroken(false);
  }, [imageSrc]);

  return (
    <div className={cn("group flex w-full", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "flex flex-col",
          isUser ? "max-w-[82%] items-end" : "w-full items-start"
        )}
      >
        {isUser ? (
          <div className="rounded-3xl bg-[#f4f4f4] px-4 py-2.5 text-sm leading-relaxed text-[#1a1a1a]">
            {imageSrc && !imageBroken && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={imageSrc}
                alt="Uploaded image"
                className="mb-2 max-h-52 max-w-full rounded-2xl border border-black/10 bg-white object-contain"
                onError={() => setImageBroken(true)}
              />
            )}
            {imageSrc && imageBroken && (
              <div className="mb-2 rounded-lg border border-dashed border-black/20 bg-white/90 px-3 py-2 text-xs text-muted-foreground">
                Failed to load image. Refresh or upload again.
              </div>
            )}
            {userText ? (
              <div className="whitespace-pre-wrap break-words">{userText}</div>
            ) : null}
          </div>
        ) : (
          <div className="w-full max-w-[82%]">
            {imageSrc && !imageBroken && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={imageSrc}
                alt="Uploaded image"
                className="mb-2 max-h-52 max-w-full rounded-2xl border border-black/10 bg-white object-contain"
                onError={() => setImageBroken(true)}
              />
            )}
            {imageSrc && imageBroken && (
              <div className="mb-2 rounded-lg border border-dashed border-black/20 bg-white/90 px-3 py-2 text-xs text-muted-foreground">
                Failed to load image. Refresh or upload again.
              </div>
            )}
            <div className="prose-sm max-w-none break-words text-foreground">
              <ChatMarkdownContent content={content} />
              {isStreaming && <TypingCursor />}
            </div>
          </div>
        )}

        {/* Actions — only for assistant messages, not while streaming */}
        {!isUser && !isStreaming && content && (
          <MessageActions
            content={content}
            onRegenerate={onRegenerate}
            showRegenerate={!!onRegenerate}
          />
        )}
      </div>
    </div>
  );
});

/* ── Main component ──────────────────────────────────────── */
export function ChatMessageList({
  messages,
  streamingContent = "",
  isStreaming,
  onRegenerate,
}: ChatMessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const isUserScrollingRef = useRef(false);
  const lastScrollTopRef = useRef(0);
  const [showScrollButton, setShowScrollButton] = useState(false);

  /* Detect when user manually scrolls up */
  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const { scrollTop, scrollHeight, clientHeight } = el;
    const atBottom = scrollHeight - scrollTop - clientHeight < 80;

    if (scrollTop < lastScrollTopRef.current) {
      // scrolling up
      isUserScrollingRef.current = true;
    }
    if (atBottom) {
      isUserScrollingRef.current = false;
    }
    lastScrollTopRef.current = scrollTop;
    setShowScrollButton(!atBottom);
  }, []);

  /* Auto-scroll while streaming unless user scrolled up */
  useEffect(() => {
    if (isUserScrollingRef.current) return;
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [streamingContent]);

  /* Scroll to bottom when new messages arrive (user sent) */
  useEffect(() => {
    isUserScrollingRef.current = false;
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const scrollToBottom = useCallback(() => {
    isUserScrollingRef.current = false;
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  /* Memoize last assistant message index for regenerate */
  const lastAssistantIndex = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return i;
    }
    return -1;
  }, [messages]);

  return (
    <div className="relative flex-1 min-h-0">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto scroll-smooth"
      >
        <div className="mx-auto max-w-3xl space-y-6 px-4 py-6 md:px-6">
          {messages.map((msg, i) => (
            <MessageBubble
              key={msg.id}
              role={msg.role}
              content={msg.content}
              displayContent={msg.display_content}
              imagePath={msg.image_path}
              localPreview={msg.local_preview}
              onRegenerate={
                i === lastAssistantIndex && onRegenerate
                  ? () => onRegenerate(i)
                  : undefined
              }
            />
          ))}

          {isStreaming && !streamingContent && <ThinkingDots />}

          {isStreaming && streamingContent && (
            <MessageBubble
              role="assistant"
              content={streamingContent}
              isStreaming
            />
          )}

          <div ref={bottomRef} className="h-1" />
        </div>
      </div>

      {/* Scroll to bottom button */}
      {showScrollButton && (
        <button
          type="button"
          onClick={scrollToBottom}
          className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-1.5 rounded-full border border-border bg-background px-3 py-1.5 text-xs text-muted-foreground shadow-md transition-all hover:bg-muted"
        >
          <ChevronDown className="size-3.5" />
          Scroll to bottom
        </button>
      )}
    </div>
  );
}
