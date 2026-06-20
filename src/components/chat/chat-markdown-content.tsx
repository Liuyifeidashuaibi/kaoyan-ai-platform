"use client";

import React, { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import { Check, Copy } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import "katex/dist/katex.min.css";
import "highlight.js/styles/github.css";

const CODE_BLOCK_SHELL =
  "group/code relative my-3 overflow-hidden rounded-xl border border-border/70 bg-[#f6f8fa] shadow-[0_1px_2px_rgba(15,23,42,0.04)] dark:border-border/60 dark:bg-muted/30 dark:shadow-none";

const CODE_BLOCK_PRE =
  "overflow-x-auto bg-transparent p-0 text-[13px] leading-[1.65] [&_.hljs]:!bg-transparent [&_.hljs]:!p-0 [&_.hljs]:text-[#24292f] dark:[&_.hljs]:text-foreground [&_code]:font-mono";

function CopyButton({ text, className }: { text: string; className?: string }) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = React.useCallback(() => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    });
  }, [text]);

  return (
    <Button
      variant="ghost"
      size="icon-xs"
      onClick={handleCopy}
      className={cn(
        "size-7 text-muted-foreground hover:bg-background/80 hover:text-foreground",
        className
      )}
      aria-label="Copy"
    >
      {copied ? <Check className="size-3.5 text-green-600" /> : <Copy className="size-3.5" />}
    </Button>
  );
}

function formatLanguageLabel(lang: string) {
  const map: Record<string, string> = {
    cpp: "C++",
    csharp: "C#",
    js: "JavaScript",
    ts: "TypeScript",
    py: "Python",
    sh: "Shell",
    bash: "Bash",
    yml: "YAML",
    md: "Markdown",
  };
  return map[lang] ?? lang.toUpperCase();
}

export const ChatMarkdownContent = memo(function ChatMarkdownContent({
  content,
}: {
  content: string;
}) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex, rehypeHighlight]}
      components={{
        pre({ children, ...props }) {
          const codeEl = React.isValidElement(children) ? children : null;
          const codeProps =
            codeEl?.props && typeof codeEl.props === "object"
              ? (codeEl.props as { children?: React.ReactNode; className?: string })
              : undefined;
          const code = codeProps?.children ?? "";
          const rawCode = typeof code === "string" ? code : String(code ?? "");
          const langMatch = codeProps?.className?.match(/language-([\w+-]+)/);
          const lang = langMatch?.[1];

          return (
            <div className={CODE_BLOCK_SHELL}>
              <div className="flex items-center justify-between border-b border-border/50 bg-white/70 px-3 py-1.5 dark:bg-background/40">
                <span className="text-[11px] font-medium tracking-wide text-muted-foreground">
                  {lang ? formatLanguageLabel(lang) : "Code"}
                </span>
                <CopyButton text={rawCode.trim()} className="opacity-70 hover:opacity-100" />
              </div>
              <div className="px-4 py-3.5">
                <pre {...props} className={CODE_BLOCK_PRE}>
                  {children}
                </pre>
              </div>
            </div>
          );
        },
        code({ children, className, ...props }) {
          const isBlock = className?.startsWith("language-");
          if (isBlock) {
            return (
              <code className={cn("hljs block whitespace-pre font-mono", className)} {...props}>
                {children}
              </code>
            );
          }
          return (
            <code
              className="mx-0.5 rounded-md border border-border/50 bg-background/90 px-1.5 py-0.5 font-mono text-[0.85em] text-foreground"
              {...props}
            >
              {children}
            </code>
          );
        },
        h1: ({ children }) => <h1 className="mt-4 mb-2 text-xl font-bold">{children}</h1>,
        h2: ({ children }) => <h2 className="mt-4 mb-2 text-lg font-semibold">{children}</h2>,
        h3: ({ children }) => <h3 className="mt-3 mb-1.5 text-base font-semibold">{children}</h3>,
        ul: ({ children }) => <ul className="my-2 ml-4 list-disc space-y-1">{children}</ul>,
        ol: ({ children }) => <ol className="my-2 ml-4 list-decimal space-y-1">{children}</ol>,
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
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
        blockquote: ({ children }) => (
          <blockquote className="my-3 border-l-4 border-primary/40 pl-4 text-muted-foreground italic">
            {children}
          </blockquote>
        ),
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary underline underline-offset-2 hover:text-primary/80"
          >
            {children}
          </a>
        ),
        hr: () => <hr className="my-4 border-border" />,
        p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
      }}
    >
      {content}
    </ReactMarkdown>
  );
});
