import { GraduationCap, SearchX } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: "search" | "school";
  className?: string;
  action?: React.ReactNode;
}

export function EmptyState({
  title = "暂无数据",
  description = "没有找到符合条件的内容",
  icon = "search",
  className,
  action,
}: EmptyStateProps) {
  const Icon = icon === "school" ? GraduationCap : SearchX;

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 text-center",
        className
      )}
    >
      <div className="mb-4 flex size-16 items-center justify-center rounded-full bg-muted">
        <Icon className="size-8 text-muted-foreground" />
      </div>
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-1 text-xs text-muted-foreground">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
