"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ImagePlus, Send, Square, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { resolveUploadUrl } from "@/lib/config/api";
import { cn } from "@/lib/utils";

type ChatInputProps = {
  onSend: (content: string, imagePath?: string | null) => void;
  onUploadImage: (file: File) => Promise<string>;
  onStop?: () => void;
  disabled?: boolean;
  isStreaming?: boolean;
  placeholder?: string;
};

export function ChatInput({
  onSend,
  onUploadImage,
  onStop,
  disabled,
  isStreaming,
  placeholder = "有什么问题尽管问…",
}: ChatInputProps) {
  const [content, setContent] = useState("");
  const [imagePath, setImagePath] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  /* Auto-resize textarea */
  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  useEffect(() => {
    resizeTextarea();
  }, [content, resizeTextarea]);

  const handleSend = useCallback(() => {
    const trimmed = content.trim();
    if (isStreaming) {
      onStop?.();
      return;
    }
    if (!trimmed && !imagePath) return;
    onSend(trimmed || "请分析这道题目", imagePath);
    setContent("");
    setImagePath(null);
    setPreviewUrl(null);
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }, [content, imagePath, isStreaming, onSend, onStop]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    setPreviewUrl(URL.createObjectURL(file));
    setUploading(true);
    try {
      const path = await onUploadImage(file);
      setImagePath(path);
    } catch {
      setPreviewUrl(null);
      setImagePath(null);
    } finally {
      setUploading(false);
    }
  };

  const clearImage = () => {
    setImagePath(null);
    setPreviewUrl(null);
  };

  const canSend = !!(content.trim() || imagePath);
  const showStop = isStreaming;

  return (
    <div className="shrink-0 border-t border-border bg-background/95 px-4 py-3 backdrop-blur md:px-6">
      <div className="mx-auto max-w-3xl">
        {/* Image preview strip */}
        {(previewUrl || imagePath) && (
          <div className="mb-2">
            <div className="relative inline-block">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={previewUrl ?? resolveUploadUrl(imagePath)}
                alt="预览"
                className="max-h-28 rounded-xl border border-border object-contain"
              />
              {uploading && (
                <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-black/40">
                  <div className="size-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                </div>
              )}
              <button
                type="button"
                onClick={clearImage}
                className="absolute -top-1.5 -right-1.5 flex size-5 items-center justify-center rounded-full bg-foreground/80 text-background hover:bg-foreground"
                aria-label="移除图片"
              >
                <X className="size-3" />
              </button>
            </div>
          </div>
        )}

        {/* Input row */}
        <div className="flex items-end gap-2 rounded-2xl border border-border bg-muted/30 px-3 py-2 focus-within:border-primary/50 focus-within:bg-background transition-colors">
          {/* Image upload button */}
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleFileChange}
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={disabled || uploading || isStreaming}
            className={cn(
              "mb-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg transition-colors",
              disabled || isStreaming
                ? "cursor-not-allowed text-muted-foreground/40"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
            aria-label="上传图片"
          >
            <ImagePlus className="size-4.5" />
          </button>

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isStreaming ? "AI 正在回答中…" : placeholder}
            disabled={disabled && !isStreaming}
            rows={1}
            className="flex-1 resize-none bg-transparent py-1.5 text-sm leading-relaxed outline-none placeholder:text-muted-foreground/60 disabled:cursor-not-allowed"
            style={{ maxHeight: "200px" }}
          />

          {/* Send / Stop button */}
          <button
            type="button"
            onClick={handleSend}
            disabled={!showStop && (disabled || uploading || !canSend)}
            className={cn(
              "mb-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg transition-colors",
              showStop
                ? "bg-foreground text-background hover:bg-foreground/80"
                : canSend && !disabled
                  ? "bg-primary text-primary-foreground hover:bg-primary/90"
                  : "cursor-not-allowed bg-muted text-muted-foreground/40"
            )}
            aria-label={showStop ? "停止生成" : "发送"}
          >
            {showStop ? (
              <Square className="size-3.5 fill-current" />
            ) : (
              <Send className="size-3.5" />
            )}
          </button>
        </div>

        <p className="mt-1.5 text-center text-[11px] text-muted-foreground/50">
          Enter 发送 · Shift+Enter 换行 · 可上传数学题图片
        </p>
      </div>
    </div>
  );
}
