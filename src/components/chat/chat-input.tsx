"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ImagePlus, Send, Square, X } from "lucide-react";

import { cn } from "@/lib/utils";

const ALLOWED_MIME = new Set([
  "image/jpeg",
  "image/png",
  "image/gif",
  "image/webp",
]);
const ALLOWED_EXT = new Set(["jpg", "jpeg", "png", "gif", "webp"]);
const HEIC_EXT = new Set(["heic", "heif"]);
const HEIC_MIME = new Set(["image/heic", "image/heif"]);
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;

type ImageAttachState = "idle" | "loading" | "ready" | "error";

export type ChatSendPayload = {
  content: string;
  imageFile: File | null;
  previewUrl: string | null;
};

type ChatInputProps = {
  onSend: (payload: ChatSendPayload) => void;
  onStop?: () => void;
  disabled?: boolean;
  isStreaming?: boolean;
  placeholder?: string;
};

function isAllowedImageFile(file: File): boolean {
  if (ALLOWED_MIME.has(file.type)) return true;
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  return ALLOWED_EXT.has(ext);
}

export function ChatInput({
  onSend,
  onStop,
  disabled,
  isStreaming,
  placeholder = "有什么问题尽管问…",
}: ChatInputProps) {
  const [content, setContent] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageState, setImageState] = useState<ImageAttachState>("idle");
  const [imageHint, setImageHint] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const previewUrlRef = useRef<string | null>(null);

  const revokePreview = useCallback(() => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    setPreviewUrl(null);
  }, []);

  useEffect(() => () => revokePreview(), [revokePreview]);

  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  useEffect(() => {
    resizeTextarea();
  }, [content, resizeTextarea]);

  const clearImage = useCallback(() => {
    revokePreview();
    setImageFile(null);
    setImageState("idle");
    setImageHint(null);
  }, [revokePreview]);

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      e.target.value = "";
      if (!file) return;

      const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
      if (HEIC_MIME.has(file.type) || HEIC_EXT.has(ext)) {
        clearImage();
        setImageState("error");
        setImageHint(
          "iPhone 的 HEIC 格式暂不支持。请在相册选「最兼容」/ JPEG，或：设置 → 相机 → 格式 → 兼容性最佳"
        );
        return;
      }

      if (!isAllowedImageFile(file)) {
        clearImage();
        setImageState("error");
        setImageHint("仅支持 jpg、jpeg、png、gif、webp 格式图片");
        return;
      }

      if (file.size > MAX_IMAGE_BYTES) {
        clearImage();
        setImageState("error");
        setImageHint("图片过大（超过 10MB），请压缩后重试");
        return;
      }

      revokePreview();
      setImageFile(null);
      setImageState("loading");
      setImageHint("请等待图片加载完成");

      const objectUrl = URL.createObjectURL(file);
      previewUrlRef.current = objectUrl;
      setPreviewUrl(objectUrl);

      try {
        const buffer = await file.arrayBuffer();
        if (buffer.byteLength === 0) {
          throw new Error("empty file");
        }
        setImageFile(file);
        setImageState("ready");
        setImageHint(null);
      } catch {
        revokePreview();
        setImageFile(null);
        setImageState("error");
        setImageHint("图片读取失败，请重新选择");
      }
    },
    [clearImage, revokePreview]
  );

  const trimmed = content.trim();
  const hasImageSelection = imageState !== "idle";
  const imageReady = imageState === "ready" && imageFile !== null;
  const imagePending = imageState === "loading";

  const canSendTextOnly = !!trimmed && !hasImageSelection;
  const canSendWithImage = imageReady;
  const canSend = canSendTextOnly || canSendWithImage;

  const handleSend = useCallback(() => {
    if (isStreaming) {
      onStop?.();
      return;
    }
    if (imagePending) return;
    if (hasImageSelection && !imageReady) return;
    if (!canSend) return;

    const text = trimmed || (imageReady ? "请分析这道题目" : "");
    const fileToSend = imageReady ? imageFile : null;
    const previewToSend = imageReady ? previewUrlRef.current : null;

    onSend({
      content: text,
      imageFile: fileToSend,
      previewUrl: previewToSend,
    });

    setContent("");
    if (fileToSend) {
      previewUrlRef.current = null;
      setPreviewUrl(null);
      setImageFile(null);
      setImageState("idle");
      setImageHint(null);
    } else {
      clearImage();
    }
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }, [
    canSend,
    clearImage,
    hasImageSelection,
    imageFile,
    imagePending,
    imageReady,
    isStreaming,
    onSend,
    onStop,
    trimmed,
  ]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const showStop = isStreaming;
  const sendDisabled =
    !showStop &&
    (disabled || imagePending || (hasImageSelection && !imageReady) || !canSend);

  const footerHint = (() => {
    if (imagePending) return "请等待图片加载完成";
    if (hasImageSelection && imageState === "error") return imageHint;
    if (imageHint) return imageHint;
    return "Enter 发送 · Shift+Enter 换行 · 可上传数学题图片";
  })();

  const footerHintWarning =
    imagePending || (hasImageSelection && imageState === "error");

  return (
    <div className="shrink-0 border-t border-border bg-background/95 px-4 py-3 backdrop-blur md:px-6">
      <div className="mx-auto max-w-3xl">
        {previewUrl && (
          <div className="mb-2">
            <div className="relative inline-block">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={previewUrl}
                alt="已选图片预览"
                className="max-h-28 max-w-full rounded-xl border border-border object-contain bg-muted/30"
              />
              {imagePending && (
                <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-black/40">
                  <div className="size-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                </div>
              )}
              {!isStreaming && (
                <button
                  type="button"
                  onClick={clearImage}
                  className="absolute -top-1.5 -right-1.5 flex size-5 items-center justify-center rounded-full bg-foreground/80 text-background hover:bg-foreground"
                  aria-label="移除图片"
                >
                  <X className="size-3" />
                </button>
              )}
            </div>
          </div>
        )}

        <div className="flex items-end gap-2 rounded-2xl border border-border bg-muted/30 px-3 py-2 focus-within:border-primary/50 focus-within:bg-background transition-colors">
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/gif,image/webp,.jpg,.jpeg,.png,.gif,.webp"
            className="hidden"
            onChange={handleFileChange}
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={disabled || isStreaming || imagePending}
            className={cn(
              "mb-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg transition-colors",
              disabled || isStreaming || imagePending
                ? "cursor-not-allowed text-muted-foreground/40"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
            aria-label="上传图片"
          >
            <ImagePlus className="size-4.5" />
          </button>

          <textarea
            ref={textareaRef}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isStreaming
                ? "AI 正在回答中…"
                : imageReady
                  ? "可补充文字说明，或直接发送图片…"
                  : placeholder
            }
            disabled={disabled && !isStreaming}
            rows={1}
            className="flex-1 resize-none bg-transparent py-1.5 text-sm leading-relaxed outline-none placeholder:text-muted-foreground/60 disabled:cursor-not-allowed"
            style={{ maxHeight: "200px" }}
          />

          <button
            type="button"
            onClick={handleSend}
            disabled={sendDisabled}
            className={cn(
              "mb-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg transition-colors",
              showStop
                ? "bg-foreground text-background hover:bg-foreground/80"
                : canSend && !disabled && !imagePending
                  ? "bg-primary text-primary-foreground hover:bg-primary/90"
                  : "cursor-not-allowed bg-muted text-muted-foreground/40"
            )}
            aria-label={showStop ? "停止生成" : "发送"}
            title={imagePending ? "请等待图片加载完成" : undefined}
          >
            {showStop ? (
              <Square className="size-3.5 fill-current" />
            ) : (
              <Send className="size-3.5" />
            )}
          </button>
        </div>

        <p
          className={cn(
            "mt-1.5 text-center text-[11px]",
            footerHintWarning
              ? "text-amber-600 dark:text-amber-400"
              : "text-muted-foreground/50"
          )}
        >
          {footerHint}
        </p>
      </div>
    </div>
  );
}
