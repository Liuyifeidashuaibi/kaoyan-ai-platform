"use client";

import { useRef } from "react";
import { cn } from "@/lib/utils";

interface TabItem {
  value: string;
  label: string;
}

interface TabNavProps {
  tabs: TabItem[];
  active: string;
  onChange: (value: string) => void;
  className?: string;
  /** 选中态颜色，默认橙色 */
  activeColor?: "orange" | "primary";
}

/**
 * 横向可滚动标签导航（详情页/分类页通用）
 */
export function TabNav({
  tabs,
  active,
  onChange,
  className,
  activeColor = "orange",
}: TabNavProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const handleClick = (value: string, idx: number) => {
    onChange(value);
    // 将当前 tab 滚动到中央
    const container = scrollRef.current;
    if (!container) return;
    const buttons = container.querySelectorAll("button");
    const btn = buttons[idx] as HTMLElement | undefined;
    if (!btn) return;
    const containerCenter = container.offsetWidth / 2;
    const btnCenter = btn.offsetLeft + btn.offsetWidth / 2;
    container.scrollTo({
      left: btnCenter - containerCenter,
      behavior: "smooth",
    });
  };

  return (
    <div
      ref={scrollRef}
      className={cn(
        "flex overflow-x-auto scrollbar-none border-b border-border bg-background",
        className
      )}
      style={{ scrollbarWidth: "none" }}
    >
      {tabs.map((tab, idx) => (
        <button
          key={tab.value}
          onClick={() => handleClick(tab.value, idx)}
          className={cn(
            "shrink-0 px-4 py-3 text-sm font-medium transition-colors relative whitespace-nowrap",
            active === tab.value
              ? activeColor === "orange"
                ? "text-orange-500"
                : "text-primary"
              : "text-muted-foreground"
          )}
        >
          {tab.label}
          {active === tab.value && (
            <span
              className={cn(
                "absolute bottom-0 left-3 right-3 h-0.5 rounded-full",
                activeColor === "orange" ? "bg-orange-500" : "bg-primary"
              )}
            />
          )}
        </button>
      ))}
    </div>
  );
}
