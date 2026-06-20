import { cn } from "@/lib/utils";

type AdminPlaceholderProps = {
  title: string;
  description?: string;
  className?: string;
};

export function AdminPlaceholder({
  title,
  description = "功能开发中，骨架已就绪。",
  className,
}: AdminPlaceholderProps) {
  return (
    <div
      className={cn(
        "flex min-h-[320px] flex-col items-center justify-center rounded-xl border border-dashed border-border/80 bg-card/50 px-6 py-16 text-center",
        className
      )}
    >
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">{description}</p>
    </div>
  );
}
