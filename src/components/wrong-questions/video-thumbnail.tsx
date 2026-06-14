"use client";

import { useEffect, useState } from "react";
import { FileVideo, Play } from "lucide-react";

import { cn } from "@/lib/utils";

type VideoThumbnailProps = {
  src: string;
  alt: string;
  className?: string;
  /** 截取第几秒作为封面，默认 0.5 */
  seekSeconds?: number;
};

/**
 * 从视频 URL 截取一帧作为封面（列表缩略图）。
 */
export function VideoThumbnail({
  src,
  alt,
  className,
  seekSeconds = 0.5,
}: VideoThumbnailProps) {
  const [poster, setPoster] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setPoster(null);
    setFailed(false);

    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.preload = "auto";
    video.src = src;

    let cancelled = false;

    const cleanup = () => {
      video.onloadeddata = null;
      video.onseeked = null;
      video.onerror = null;
      video.removeAttribute("src");
      video.load();
    };

    video.onerror = () => {
      if (!cancelled) setFailed(true);
      cleanup();
    };

    video.onloadeddata = () => {
      const target = Number.isFinite(video.duration)
        ? Math.min(seekSeconds, Math.max(0, video.duration - 0.1))
        : seekSeconds;
      video.currentTime = target;
    };

    video.onseeked = () => {
      if (cancelled || !video.videoWidth || !video.videoHeight) {
        if (!cancelled) setFailed(true);
        cleanup();
        return;
      }

      try {
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          setFailed(true);
          cleanup();
          return;
        }
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        setPoster(canvas.toDataURL("image/jpeg", 0.82));
      } catch {
        setFailed(true);
      }
      cleanup();
    };

    return () => {
      cancelled = true;
      cleanup();
    };
  }, [src, seekSeconds]);

  if (failed) {
    return (
      <div
        className={cn(
          "flex size-full flex-col items-center justify-center gap-1 bg-violet-500/10 text-violet-600",
          className
        )}
      >
        <FileVideo className="size-8" />
        <span className="text-[10px]">视频</span>
      </div>
    );
  }

  if (!poster) {
    return (
      <div
        className={cn(
          "flex size-full items-center justify-center bg-muted text-muted-foreground",
          className
        )}
      >
        <FileVideo className="size-8 animate-pulse" />
      </div>
    );
  }

  return (
    <div className={cn("relative size-full", className)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={poster} alt={alt} className="size-full object-cover" />
      <span className="absolute inset-0 flex items-center justify-center bg-black/25">
        <span className="flex size-10 items-center justify-center rounded-full bg-black/55 text-white">
          <Play className="size-5 fill-current pl-0.5" />
        </span>
      </span>
    </div>
  );
}
