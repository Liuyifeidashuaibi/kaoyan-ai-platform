"use client";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type PaperToolbarProps = {
  title: string;
  onTitleChange?: (title: string) => void;
  stats?: string;
  actions?: React.ReactNode;
  className?: string;
};

/**
 * 试卷顶部操作栏 — 可编辑标题、统计信息、操作按钮区。
 */
export function PaperToolbar({
  title,
  onTitleChange,
  stats,
  actions,
  className,
}: PaperToolbarProps) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-3 border-b px-4 py-3",
        className
      )}
    >
      <div className="flex min-w-0 flex-1 items-center gap-2">
        {onTitleChange ? (
          <Input
            value={title}
            onChange={(e) => onTitleChange(e.target.value)}
            className="h-8 max-w-xs border-0 bg-transparent px-0 text-base font-semibold shadow-none focus-visible:ring-1"
          />
        ) : (
          <h2 className="truncate text-base font-semibold">{title}</h2>
        )}
      </div>
      {stats && (
        <span className="text-muted-foreground text-xs tabular-nums">
          {stats}
        </span>
      )}
      {actions && (
        <div className="flex items-center gap-1.5">{actions}</div>
      )}
    </div>
  );
}
