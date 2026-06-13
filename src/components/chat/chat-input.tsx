"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ImagePlus, Loader2, Mic, Send, Square, Volume2, X } from "lucide-react";

import { transcribeAudio } from "@/lib/api/chat";
import { WavRecorder } from "@/lib/audio/wav-recorder";
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
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MAX_AUDIO_SECONDS = 30;

type ImageAttachState = "idle" | "loading" | "ready" | "error";

export type ChatSendPayload = {
  content: string;
  imageFile: File | null;
  previewUrl: string | null;
  audioFile: Blob | null;
  enableTts: boolean;
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

function formatSeconds(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function appendTranscript(prev: string, next: string): string {
  const a = prev.trimEnd();
  const b = next.trim();
  if (!b) return a;
  if (!a) return b;
  return `${a} ${b}`;
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
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [enableTts, setEnableTts] = useState(false);

  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const previewUrlRef = useRef<string | null>(null);
  const wavRecorderRef = useRef<WavRecorder | null>(null);
  const recordTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const revokePreview = useCallback(() => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    setPreviewUrl(null);
  }, []);

  useEffect(() => () => {
    revokePreview();
    if (recordTimerRef.current) clearInterval(recordTimerRef.current);
    if (wavRecorderRef.current?.isActive) {
      wavRecorderRef.current.stop();
    }
  }, [revokePreview]);

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

  const transcribeAndAppend = useCallback(async (wav: Blob) => {
    setIsTranscribing(true);
    setImageHint("正在识别语音…");
    try {
      const text = await transcribeAudio(wav);
      setContent((prev) => appendTranscript(prev, text));
      setImageHint(null);
      requestAnimationFrame(() => {
        textareaRef.current?.focus();
        const el = textareaRef.current;
        if (el) {
          el.selectionStart = el.selectionEnd = el.value.length;
        }
      });
    } catch (e) {
      setImageHint(e instanceof Error ? e.message : "语音识别失败，请重试");
    } finally {
      setIsTranscribing(false);
      setRecordSeconds(0);
    }
  }, []);

  const stopRecording = useCallback(async () => {
    if (recordTimerRef.current) {
      clearInterval(recordTimerRef.current);
      recordTimerRef.current = null;
    }
    const recorder = wavRecorderRef.current;
    wavRecorderRef.current = null;
    setIsRecording(false);

    if (!recorder?.isActive) return;

    const wav = recorder.stop();
    if (wav.size > 0) {
      await transcribeAndAppend(wav);
    } else {
      setImageHint("录音过短，请重试");
      setRecordSeconds(0);
    }
  }, [transcribeAndAppend]);

  const startRecording = useCallback(async () => {
    if (isRecording || isTranscribing || disabled || isStreaming) return;
    try {
      const recorder = new WavRecorder();
      await recorder.start();
      wavRecorderRef.current = recorder;
      setIsRecording(true);
      setRecordSeconds(0);
      setImageHint(null);
      recordTimerRef.current = setInterval(() => {
        setRecordSeconds((s) => {
          if (s + 1 >= MAX_AUDIO_SECONDS) {
            void stopRecording();
            return MAX_AUDIO_SECONDS;
          }
          return s + 1;
        });
      }, 1000);
    } catch {
      setImageHint("无法访问麦克风，请检查浏览器权限");
    }
  }, [disabled, isRecording, isStreaming, isTranscribing, stopRecording]);

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
          "iPhone 的 HEIC 格式暂不支持。请在相册选「最兼容」/ JPEG"
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
        setImageHint("图片过大（超过 5MB），请压缩后重试");
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
        if (buffer.byteLength === 0) throw new Error("empty");
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
  const voiceBusy = isRecording || isTranscribing;

  const canSend =
    (!!trimmed && !hasImageSelection) || imageReady || (!!trimmed && imageReady);

  const handleSend = useCallback(() => {
    if (isStreaming) {
      onStop?.();
      return;
    }
    if (voiceBusy) return;
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
      audioFile: null,
      enableTts,
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
    enableTts,
    hasImageSelection,
    imageFile,
    imagePending,
    imageReady,
    isStreaming,
    onSend,
    onStop,
    trimmed,
    voiceBusy,
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
    (disabled ||
      voiceBusy ||
      imagePending ||
      (hasImageSelection && !imageReady) ||
      !canSend);

  const footerHint = (() => {
    if (isRecording) {
      return `录音中 ${formatSeconds(recordSeconds)} / 最长 ${MAX_AUDIO_SECONDS}s，再次点击麦克风结束`;
    }
    if (isTranscribing) return "正在将语音转为文字…";
    if (imagePending) return "请等待图片加载完成";
    if (hasImageSelection && imageState === "error") return imageHint;
    if (imageHint) return imageHint;
    return "麦克风录音后自动转文字到输入框，可编辑、可继续录音追加 · Enter 发送";
  })();

  const footerHintWarning =
    isRecording ||
    isTranscribing ||
    imagePending ||
    (hasImageSelection && imageState === "error") ||
    !!imageHint;

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
            disabled={disabled || isStreaming || imagePending || voiceBusy}
            className={cn(
              "mb-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg transition-colors",
              disabled || isStreaming || imagePending || voiceBusy
                ? "cursor-not-allowed text-muted-foreground/40"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
            aria-label="上传图片"
          >
            <ImagePlus className="size-4.5" />
          </button>

          <button
            type="button"
            onClick={() => {
              if (isRecording) void stopRecording();
              else void startRecording();
            }}
            disabled={disabled || isStreaming || imagePending || isTranscribing}
            className={cn(
              "mb-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg transition-colors",
              isRecording
                ? "bg-destructive text-destructive-foreground animate-pulse"
                : isTranscribing
                  ? "cursor-wait text-muted-foreground"
                  : disabled || isStreaming || imagePending
                    ? "cursor-not-allowed text-muted-foreground/40"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
            aria-label={isRecording ? "停止录音并转文字" : "语音输入"}
          >
            {isTranscribing ? (
              <Loader2 className="size-4.5 animate-spin" />
            ) : (
              <Mic className="size-4.5" />
            )}
          </button>

          <button
            type="button"
            onClick={() => setEnableTts((v) => !v)}
            disabled={disabled || isStreaming}
            title="回答完成后朗读（可选）"
            className={cn(
              "mb-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg transition-colors",
              enableTts
                ? "bg-primary/15 text-primary"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
              (disabled || isStreaming) && "cursor-not-allowed opacity-40"
            )}
            aria-label="语音播放开关"
            aria-pressed={enableTts}
          >
            <Volume2 className="size-4.5" />
          </button>

          <textarea
            ref={textareaRef}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isStreaming
                ? "AI 正在回答中…"
                : isTranscribing
                  ? "语音识别中…"
                  : imageReady
                    ? "可补充文字说明，或直接发送图片…"
                    : placeholder
            }
            disabled={(disabled && !isStreaming) || isRecording || isTranscribing}
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
                : canSend && !disabled && !imagePending && !voiceBusy
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
