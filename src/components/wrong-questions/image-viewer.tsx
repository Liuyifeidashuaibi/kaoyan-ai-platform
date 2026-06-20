"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Minus,
  Plus,
  RotateCcw,
  X,
} from "lucide-react";

import { resolveUploadUrl } from "@/lib/config/api";

type SlideItem = {
  src: string;
  title: string;
  description?: string;
};

type ImageViewerProps = {
  open: boolean;
  index: number;
  slides: SlideItem[];
  onClose: () => void;
};

const MIN_SCALE = 0.2; // 20%
const MAX_SCALE = 8; // 800%
const WHEEL_STEP = 0.0015; // 滚轮灵敏度（每 deltaY 单位的缩放比例）
const BUTTON_STEP = 0.2; // 按钮 ±20%

function clampScale(value: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, value));
}

/**
 * 错题图片查看器：鼠标滚轮缩放（以光标为中心）、百分比显示、拖拽平移、左右切换。
 */
export function ImageViewer({ open, index, slides, onClose }: ImageViewerProps) {
  const [current, setCurrent] = useState(index);
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });

  const stageRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0, ox: 0, oy: 0 });

  const resetTransform = useCallback(() => {
    setScale(1);
    setOffset({ x: 0, y: 0 });
  }, []);

  // 打开 / 切换索引时重置
  useEffect(() => {
    if (open) {
      setCurrent(index);
      resetTransform();
    }
  }, [open, index, resetTransform]);

  const slide = slides[current];

  const goTo = useCallback(
    (next: number) => {
      if (slides.length === 0) return;
      const wrapped = (next + slides.length) % slides.length;
      setCurrent(wrapped);
      resetTransform();
    },
    [slides.length, resetTransform]
  );

  const zoomAt = useCallback(
    (factor: number, clientX?: number, clientY?: number) => {
      setScale((prevScale) => {
        const nextScale = clampScale(prevScale * factor);
        if (nextScale === prevScale) return prevScale;

        const stage = stageRef.current;
        if (stage && clientX != null && clientY != null) {
          // 以光标位置为锚点缩放，保持光标下的内容不动
          const rect = stage.getBoundingClientRect();
          const cx = clientX - rect.left - rect.width / 2;
          const cy = clientY - rect.top - rect.height / 2;
          const ratio = nextScale / prevScale;
          setOffset((prev) => ({
            x: cx - (cx - prev.x) * ratio,
            y: cy - (cy - prev.y) * ratio,
          }));
        }
        return nextScale;
      });
    },
    []
  );

  // 滚轮缩放（非被动监听，才能 preventDefault 阻止页面滚动）
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage || !open) return;

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const factor = Math.exp(-e.deltaY * WHEEL_STEP);
      zoomAt(factor, e.clientX, e.clientY);
    };

    stage.addEventListener("wheel", onWheel, { passive: false });
    return () => stage.removeEventListener("wheel", onWheel);
  }, [open, zoomAt]);

  // 键盘：Esc 关闭、← → 切换、+ - 缩放、0 复位
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowLeft") goTo(current - 1);
      else if (e.key === "ArrowRight") goTo(current + 1);
      else if (e.key === "+" || e.key === "=") zoomAt(1 + BUTTON_STEP);
      else if (e.key === "-") zoomAt(1 - BUTTON_STEP);
      else if (e.key === "0") resetTransform();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, current, goTo, zoomAt, resetTransform, onClose]);

  // 打开时锁定页面滚动
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  const onPointerDown = (e: React.PointerEvent) => {
    draggingRef.current = true;
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      ox: offset.x,
      oy: offset.y,
    };
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!draggingRef.current) return;
    const { x, y, ox, oy } = dragStartRef.current;
    setOffset({ x: ox + (e.clientX - x), y: oy + (e.clientY - y) });
  };

  const endDrag = (e: React.PointerEvent) => {
    draggingRef.current = false;
    (e.target as HTMLElement).releasePointerCapture?.(e.pointerId);
  };

  if (!open || !slide) return null;

  const percent = Math.round(scale * 100);
  const hasMultiple = slides.length > 1;

  return (
    <div
      className="fixed inset-0 z-[100] flex flex-col bg-black/90 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
    >
      {/* 顶部工具栏 */}
      <div className="flex shrink-0 items-center justify-between gap-2 px-4 py-3 text-white">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{slide.title}</p>
          {slide.description && (
            <p className="truncate text-xs text-white/60">{slide.description}</p>
          )}
        </div>

        <div className="flex items-center gap-1 rounded-full bg-white/10 px-1.5 py-1">
          <button
            type="button"
            onClick={() => zoomAt(1 - BUTTON_STEP)}
            className="flex size-8 items-center justify-center rounded-full transition-colors hover:bg-white/20"
            aria-label="Zoom out"
          >
            <Minus className="size-4" />
          </button>
          <span className="min-w-[3.5rem] select-none text-center text-sm font-medium tabular-nums">
            {percent}%
          </span>
          <button
            type="button"
            onClick={() => zoomAt(1 + BUTTON_STEP)}
            className="flex size-8 items-center justify-center rounded-full transition-colors hover:bg-white/20"
            aria-label="Zoom in"
          >
            <Plus className="size-4" />
          </button>
          <button
            type="button"
            onClick={resetTransform}
            className="flex size-8 items-center justify-center rounded-full transition-colors hover:bg-white/20"
            aria-label="Reset"
            title="Reset (press 0)"
          >
            <RotateCcw className="size-4" />
          </button>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="ml-1 flex size-9 items-center justify-center rounded-full text-white transition-colors hover:bg-white/20"
          aria-label="Close"
        >
          <X className="size-5" />
        </button>
      </div>

      {/* 缩放舞台 */}
      <div
        ref={stageRef}
        className="relative flex flex-1 select-none items-center justify-center overflow-hidden"
        onDoubleClick={(e) =>
          scale > 1 ? resetTransform() : zoomAt(2, e.clientX, e.clientY)
        }
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        style={{ cursor: scale > 1 ? "grab" : "default" }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={slide.src}
          alt={slide.title}
          draggable={false}
          className="max-h-full max-w-full object-contain will-change-transform"
          style={{
            transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
            transition: draggingRef.current ? "none" : "transform 0.08s ease-out",
          }}
        />

        {hasMultiple && (
          <>
            <button
              type="button"
              onClick={() => goTo(current - 1)}
              className="absolute left-3 top-1/2 flex size-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/10 text-white transition-colors hover:bg-white/25"
              aria-label="Previous"
            >
              <ChevronLeft className="size-5" />
            </button>
            <button
              type="button"
              onClick={() => goTo(current + 1)}
              className="absolute right-3 top-1/2 flex size-10 -translate-y-1/2 items-center justify-center rounded-full bg-white/10 text-white transition-colors hover:bg-white/25"
              aria-label="Next"
            >
              <ChevronRight className="size-5" />
            </button>
          </>
        )}
      </div>

      {/* 底部提示 */}
      <div className="shrink-0 px-4 py-2 text-center text-xs text-white/50">
        Scroll to zoom · Drag to pan · Double-click to zoom/reset
        {hasMultiple ? ` · ${current + 1}/${slides.length}` : ""}
      </div>
    </div>
  );
}

function formatSlideDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Build slide list from image materials only */
export function buildSlides(
  questions: Array<{
    file_path?: string;
    image_path: string;
    title: string;
    category_name: string;
    created_at: string;
  }>
): SlideItem[] {
  return questions.map((q) => ({
    src: resolveUploadUrl(q.file_path || q.image_path),
    title: q.title,
    description: `${q.category_name} · ${formatSlideDate(q.created_at)}`,
  }));
}
