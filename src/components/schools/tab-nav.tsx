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
  /** 选中态颜色：brand=#007AFF */
  activeColor?: "orange" | "primary" | "brand";
}

/**
 * 横向可滚动标签导航（详情页/分类页通用）
 */
export function TabNav({
  tabs,
  active,
  onChange,
  className,
  activeColor = "brand",
}: TabNavProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const handleClick = (value: string, idx: number) => {
    onChange(value);
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

  const activeTextClass =
    activeColor === "brand"
      ? "text-[#007AFF]"
      : activeColor === "orange"
        ? "text-orange-500"
        : "text-primary";

  const activeBarClass =
    activeColor === "brand"
      ? "bg-[#007AFF]"
      : activeColor === "orange"
        ? "bg-orange-500"
        : "bg-primary";

  return (
    <div
      ref={scrollRef}
      className={cn(
        "flex overflow-x-auto scrollbar-none border-b border-border bg-white",
        className
      )}
      style={{ scrollbarWidth: "none" }}
    >
      {tabs.map((tab, idx) => (
        <button
          key={tab.value}
          onClick={() => handleClick(tab.value, idx)}
          className={cn(
            "shrink-0 px-4 py-3 text-sm font-medium transition-colors relative whitespace-nowrap text-[#111827]/60",
            active === tab.value ? activeTextClass : "hover:text-[#111827]"
          )}
        >
          {tab.label}
          {active === tab.value && (
            <span
              className={cn(
                "absolute bottom-0 left-3 right-3 h-0.5 rounded-full",
                activeBarClass
              )}
            />
          )}
        </button>
      ))}
    </div>
  );
}
