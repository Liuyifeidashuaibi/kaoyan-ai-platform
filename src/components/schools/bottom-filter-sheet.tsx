"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface FilterOption {
  value: string;
  label: string;
}

interface BottomFilterSheetProps {
  open: boolean;
  onClose: () => void;
  title: string;
  options: FilterOption[];
  selected: string;
  onSelect: (value: string) => void;
  allLabel?: string;
}

/**
 * 通用底部弹出筛选面板（用于年份/学位类型/学习方式等下拉）
 */
export function BottomFilterSheet({
  open,
  onClose,
  title,
  options,
  selected,
  onSelect,
  allLabel = "不限",
}: BottomFilterSheetProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  // 阻止背景滚动
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  if (!open) return null;

  const allOptions = [{ value: "", label: allLabel }, ...options];

  return (
    <div className="fixed inset-0 z-50 flex items-end">
      {/* 遮罩 */}
      <div
        ref={overlayRef}
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* 面板 */}
      <div className="relative w-full bg-background rounded-t-2xl shadow-xl max-h-[60vh] flex flex-col">
        {/* 标题栏 */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <span className="text-sm font-semibold">{title}</span>
          <button
            onClick={onClose}
            className="p-1 rounded-full hover:bg-muted"
            aria-label="关闭"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* 选项列表 */}
        <div className="overflow-y-auto flex-1 py-2">
          {allOptions.map((opt) => (
            <button
              key={opt.value}
              onClick={() => {
                onSelect(opt.value);
                onClose();
              }}
              className={cn(
                "w-full flex items-center justify-between px-4 py-3 text-sm",
                "hover:bg-muted/50 transition-colors",
                selected === opt.value &&
                  "text-[#007AFF] font-medium"
              )}
            >
              <span>{opt.label}</span>
              {selected === opt.value && (
                <svg
                  className="size-4 text-[#007AFF]"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
