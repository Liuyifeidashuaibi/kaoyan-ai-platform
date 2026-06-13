"use client";

import { useEffect, useRef } from "react";
import { Search, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface SchoolSearchOverlayProps {
  open: boolean;
  value: string;
  onChange: (value: string) => void;
  onClose: () => void;
}

/** 右侧搜索图标触发的快捷检索浮层 */
export function SchoolSearchOverlay({
  open,
  value,
  onChange,
  onClose,
}: SchoolSearchOverlayProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
      const t = setTimeout(() => inputRef.current?.focus(), 50);
      return () => {
        clearTimeout(t);
        document.body.style.overflow = "";
      };
    }
    document.body.style.overflow = "";
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col">
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative bg-white shadow-lg">
        <div className="mx-auto flex max-w-7xl items-center gap-2 px-4 py-3 lg:px-8">
          <Search className="size-5 shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            type="search"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="搜索院校或专业关键字"
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          {value && (
            <button
              type="button"
              onClick={() => onChange("")}
              className="p-0.5 text-muted-foreground hover:text-foreground"
              aria-label="清除"
            >
              <X className="size-4" />
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className={cn(
              "shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium",
              "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
            )}
          >
            取消
          </button>
        </div>
      </div>
    </div>
  );
}
