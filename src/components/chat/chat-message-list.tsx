"use client";

import React, {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import { Bot, Check, ChevronDown, Copy, RefreshCw, ThumbsDown, ThumbsUp, User } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ChatMessage } from "@/lib/api/types";
import { resolveUploadUrl } from "@/lib/config/api";
import { cn } from "@/lib/utils";

/* ── KaTeX CSS (loaded once) ─────────────────────────────── */
import "katex/dist/katex.min.css";
import "highlight.js/styles/github.css";

/* ── Types ───────────────────────────────────────────────── */
type MessageActionsProps = {
  content: string;
  onRegenerate?: () => void;
  showRegenerate?: boolean;
};

type MessageBubbleProps = {
  role: string;
  content: string;
  imagePath?: string | null;
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
      aria-label="复制"
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
        aria-label="赞"
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
        aria-label="踩"
      >
        <ThumbsDown className="size-3.5" />
      </Button>
      {showRegenerate && onRegenerate && (
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={onRegenerate}
          className="size-7 text-muted-foreground hover:text-foreground"
          aria-label="重新生成"
        >
          <RefreshCw className="size-3.5" />
        </Button>
      )}
    </div>
  );
});

/* ── Markdown renderer ───────────────────────────────────── */
const MarkdownContent = memo(function MarkdownContent({
  content,
}: {
  content: string;
}) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex, rehypeHighlight]}
      components={{
        /* Code blocks */
        pre({ children, ...props }) {
          const codeEl = React.isValidElement(children) ? children : null;
          const code =
            codeEl?.props &&
            typeof codeEl.props === "object" &&
            "children" in codeEl.props
              ? (codeEl.props as { children?: React.ReactNode }).children
              : "";
          const rawCode = typeof code === "string" ? code : String(code ?? "");

          return (
            <div className="group/code relative my-3">
              <CopyButton
                text={rawCode.trim()}
                className="absolute top-2 right-2 opacity-0 group-hover/code:opacity-100"
              />
              <pre
                {...props}
                className="overflow-x-auto rounded-lg bg-zinc-950 p-4 text-sm text-zinc-100 dark:bg-zinc-900"
              >
                {children}
              </pre>
            </div>
          );
        },
        /* Inline code */
        code({ children, className, ...props }) {
          const isBlock = className?.startsWith("language-");
          if (isBlock) return <code className={className} {...props}>{children}</code>;
          return (
            <code
              className="mx-0.5 rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[0.85em] text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200"
              {...props}
            >
              {children}
            </code>
          );
        },
        /* Headings */
        h1: ({ children }) => <h1 className="mt-4 mb-2 text-xl font-bold">{children}</h1>,
        h2: ({ children }) => <h2 className="mt-4 mb-2 text-lg font-semibold">{children}</h2>,
        h3: ({ children }) => <h3 className="mt-3 mb-1.5 text-base font-semibold">{children}</h3>,
        /* Lists */
        ul: ({ children }) => <ul className="my-2 ml-4 list-disc space-y-1">{children}</ul>,
        ol: ({ children }) => <ol className="my-2 ml-4 list-decimal space-y-1">{children}</ol>,
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
        /* Table */
        table: ({ children }) => (
          <div className="my-3 overflow-x-auto rounded-lg border border-border">
            <table className="min-w-full text-sm">{children}</table>
          </div>
        ),
        thead: ({ children }) => <thead className="bg-muted">{children}</thead>,
        th: ({ children }) => (
          <th className="px-3 py-2 text-left font-medium">{children}</th>
        ),
        td: ({ children }) => (
          <td className="border-t border-border px-3 py-2">{children}</td>
        ),
        /* Blockquote */
        blockquote: ({ children }) => (
          <blockquote className="my-3 border-l-4 border-primary/40 pl-4 text-muted-foreground italic">
            {children}
          </blockquote>
        ),
        /* Horizontal rule */
        hr: () => <hr className="my-4 border-border" />,
        /* Paragraph */
        p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
        /* Strong / Em */
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
      }}
    >
      {content}
    </ReactMarkdown>
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
      <span>思考中…</span>
    </div>
  );
}

/* ── Single message bubble ───────────────────────────────── */
const MessageBubble = memo(function MessageBubble({
  role,
  content,
  imagePath,
  isStreaming,
  onRegenerate,
}: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <div className={cn("group flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
      {/* Avatar */}
      <div
        className={cn(
          "mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg text-sm",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-gradient-to-br from-violet-500 to-indigo-600 text-white"
        )}
      >
        {isUser ? <User className="size-4" /> : <Bot className="size-4" />}
      </div>

      {/* Content */}
      <div className={cn("flex max-w-[82%] flex-col", isUser ? "items-end" : "items-start")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm leading-relaxed",
            isUser
              ? "rounded-tr-sm bg-primary text-primary-foreground"
              : "rounded-tl-sm bg-muted/60 text-foreground"
          )}
        >
          {imagePath && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={resolveUploadUrl(imagePath)}
              alt="上传图片"
              className="mb-2 max-h-52 rounded-lg object-contain"
            />
          )}
          {isUser ? (
            <div className="whitespace-pre-wrap break-words">{content}</div>
          ) : (
            <div className="prose-sm max-w-none break-words">
              <MarkdownContent content={content} />
              {isStreaming && <TypingCursor />}
            </div>
          )}
        </div>

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
          {messages.length === 0 && !isStreaming && (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <div className="mb-4 flex size-16 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 text-white shadow-lg">
                <Bot className="size-8" />
              </div>
              <h2 className="text-xl font-semibold">考研 AI 助手</h2>
              <p className="mt-3 max-w-sm text-sm text-muted-foreground leading-relaxed">
                你的专属考研辅导老师，解答数学、英语、政治等全科问题。
                <br />
                支持上传题目图片，获得分步解析。
              </p>
            </div>
          )}

          {messages.map((msg, i) => (
            <MessageBubble
              key={msg.id}
              role={msg.role}
              content={msg.content}
              imagePath={msg.image_path}
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
          回到底部
        </button>
      )}
    </div>
  );
}
