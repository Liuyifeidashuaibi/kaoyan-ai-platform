"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";

export interface FilterOption {
  value: string;
  label: string;
}

interface FilterDropdownProps {
  label: string;
  value: string;
  options: FilterOption[];
  onChange: (value: string) => void;
  className?: string;
  /** 下拉列表最大高度，超出可滚动（默认约 5 项） */
  maxVisibleItems?: number;
  /** 双栏专业类别筛选 */
  dualColumn?: {
    leftOptions: FilterOption[];
    rightOptions: FilterOption[];
    leftValue: string;
    rightValue: string;
    onLeftChange: (value: string) => void;
    onRightChange: (value: string) => void;
  };
}

export function FilterDropdown({
  label,
  value,
  options,
  onChange,
  className,
  maxVisibleItems = 5,
  dualColumn,
}: FilterDropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const active = dualColumn
    ? dualColumn.leftValue !== "全部" || dualColumn.rightValue !== "全部"
    : value !== "全部" && value !== "";

  const displayLabel = dualColumn
    ? dualColumn.rightValue !== "全部"
      ? dualColumn.rightValue
      : dualColumn.leftValue !== "全部"
        ? dualColumn.leftValue
        : label
    : value !== "全部" && value
      ? options.find((o) => o.value === value)?.label ?? value
      : label;

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleSelect = (v: string) => {
    onChange(v);
    setOpen(false);
  };

  return (
    <div ref={ref} className={cn("relative", className)}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm transition-colors",
          active ? "font-medium text-orange-500" : "text-muted-foreground hover:text-foreground"
        )}
      >
        {displayLabel}
        {open ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 min-w-[160px] rounded-xl bg-white py-1 shadow-lg ring-1 ring-black/5">
          {dualColumn ? (
            <div className="flex">
              <div className="max-h-64 w-40 overflow-y-auto border-r border-border/60 py-1">
                {dualColumn.leftOptions.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => {
                      dualColumn.onLeftChange(opt.value);
                      dualColumn.onRightChange("全部");
                    }}
                    className={cn(
                      "flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-muted/50",
                      dualColumn.leftValue === opt.value && "font-medium text-orange-500"
                    )}
                  >
                    <span className="truncate">{opt.label}</span>
                    {dualColumn.leftValue === opt.value && (
                      <Check className="size-4 shrink-0 text-orange-500" />
                    )}
                  </button>
                ))}
              </div>
              <div className="max-h-64 w-44 overflow-y-auto py-1">
                {dualColumn.rightOptions.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => {
                      dualColumn.onRightChange(opt.value);
                      setOpen(false);
                    }}
                    className={cn(
                      "flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-muted/50",
                      dualColumn.rightValue === opt.value && "font-medium text-orange-500"
                    )}
                  >
                    <span className="truncate">{opt.label}</span>
                    {dualColumn.rightValue === opt.value && (
                      <Check className="size-4 shrink-0 text-orange-500" />
                    )}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div
              className="overflow-y-auto overscroll-contain py-1"
              style={{ maxHeight: `${maxVisibleItems * 40}px` }}
            >
              {options.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => handleSelect(opt.value)}
                  className={cn(
                    "flex w-full items-center justify-between px-4 py-2.5 text-left text-sm hover:bg-muted/50",
                    value === opt.value && "font-medium text-orange-500"
                  )}
                >
                  {opt.label}
                  {value === opt.value && <Check className="size-4 text-orange-500" />}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
