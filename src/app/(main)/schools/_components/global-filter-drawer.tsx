"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { useSchoolsFilter } from "../_context/schools-filter-context";
import type { SchoolsGlobalFilter } from "../_context/schools-filter-context";

interface GlobalFilterDrawerProps {
  open: boolean;
  onClose: () => void;
}

/**
 * 985/211/双一流全局筛选弹窗
 */
export function GlobalFilterDrawer({ open, onClose }: GlobalFilterDrawerProps) {
  const { filter, setFilter } = useSchoolsFilter();
  const [draft, setDraft] = useState<SchoolsGlobalFilter>(filter);
  const overlayRef = useRef<HTMLDivElement>(null);

  // 每次打开同步最新 filter
  useEffect(() => {
    if (open) setDraft(filter);
  }, [open, filter]);

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

  const hasAny = draft.level985 || draft.level211 || draft.doubleFirstClass;

  const handleToggle = (key: keyof SchoolsGlobalFilter) => {
    const next = { ...draft, [key]: !draft[key] };
    // 防呆：至少一项为 true
    if (!next.level985 && !next.level211 && !next.doubleFirstClass) return;
    setDraft(next);
  };

  const handleConfirm = () => {
    if (!hasAny) return;
    setFilter(draft);
    onClose();
  };

  const handleReset = () => {
    const all: SchoolsGlobalFilter = {
      level985: true,
      level211: true,
      doubleFirstClass: true,
    };
    setDraft(all);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end">
      <div
        ref={overlayRef}
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative w-full bg-background rounded-t-2xl shadow-xl">
        {/* 标题 */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <button
            onClick={handleReset}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            重置
          </button>
          <span className="text-sm font-semibold">院校层次</span>
          <button
            onClick={onClose}
            className="p-1 rounded-full hover:bg-muted"
            aria-label="关闭"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* 内容 */}
        <div className="px-4 py-5 space-y-4">
          <p className="text-xs text-muted-foreground">院校层次（至少选一项）</p>

          <div className="space-y-3">
            {(
              [
                { key: "level985", label: "985高校", desc: "共39所" },
                { key: "level211", label: "211高校", desc: "共116所（含985）" },
                {
                  key: "doubleFirstClass",
                  label: "双一流高校",
                  desc: "一流大学/一流学科建设高校",
                },
              ] as { key: keyof SchoolsGlobalFilter; label: string; desc: string }[]
            ).map(({ key, label, desc }) => (
              <button
                key={key}
                onClick={() => handleToggle(key)}
                className="flex w-full items-center justify-between rounded-xl border border-border px-4 py-3 text-left transition-colors active:bg-muted/50"
              >
                <div>
                  <p className="text-sm font-medium">{label}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>
                </div>
                {/* 复选框 */}
                <div
                  className={`size-5 rounded flex items-center justify-center border-2 transition-colors ${
                    draft[key]
                      ? "bg-[#111827] border-[#111827]"
                      : "border-border"
                  }`}
                >
                  {draft[key] && (
                    <svg
                      viewBox="0 0 12 10"
                      fill="none"
                      className="size-3"
                      stroke="white"
                      strokeWidth={2}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M1 5l3.5 3.5L11 1" />
                    </svg>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* 确认按钮 */}
        <div className="px-4 pb-8 pt-2">
          <button
            onClick={handleConfirm}
            disabled={!hasAny}
            className="w-full rounded-xl bg-[#111827] py-3 text-sm font-semibold text-white disabled:opacity-50 active:bg-[#111827] transition-colors"
          >
            确认筛选
          </button>
        </div>
      </div>
    </div>
  );
}
