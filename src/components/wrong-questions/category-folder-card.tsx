"use client";

import { Folder } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
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
    <Card
      className={cn(
        "cursor-pointer transition-all hover:border-primary/40 hover:shadow-md",
        className
      )}
      onClick={onClick}
    >
      <CardContent className="flex flex-col items-center gap-3 p-6 text-center">
        <div className="flex size-16 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
          <Folder className="size-9" strokeWidth={1.5} />
        </div>
        <div className="space-y-1">
          <p className="text-base font-semibold">{category.name}</p>
          <p className="text-sm text-muted-foreground">
            {category.question_count} 条资料
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
