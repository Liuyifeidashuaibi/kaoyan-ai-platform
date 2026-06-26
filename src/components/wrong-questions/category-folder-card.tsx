"use client";

import { ChevronRight } from "lucide-react";

import type { WrongQuestionCategory } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type CategoryFolderCardProps = {
  category: WrongQuestionCategory;
  onClick: () => void;
  className?: string;
};

export function CategoryFolderCard({
  category,
  onClick,
  className,
}: CategoryFolderCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group relative flex w-full items-center justify-between gap-4 border-b border-border/50 px-5 py-4 text-left transition-colors hover:bg-muted/30",
        className
      )}
    >
      {/* Left accent line on hover */}
      <span className="absolute left-0 top-0 h-full w-0.5 bg-foreground opacity-0 transition-opacity group-hover:opacity-100" />

      <div className="flex min-w-0 flex-1 items-center gap-3">
        <span className="size-1.5 shrink-0 rounded-full bg-foreground/20 transition-colors group-hover:bg-foreground" />
        <p className="truncate text-sm font-medium text-foreground">
          {category.name}
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        <span className="text-xs tabular-nums text-muted-foreground">
          {category.question_count} items
        </span>
        <ChevronRight className="size-4 text-muted-foreground/40 transition-all group-hover:translate-x-0.5 group-hover:text-foreground/60" />
      </div>
    </button>
  );
}
