import { cn } from "@/lib/utils";

const statusColors = {
  idle: "bg-muted-foreground/40",
  running: "bg-emerald-500",
  warning: "bg-amber-500",
  error: "bg-red-500",
} as const;

export type StatusDotVariant = keyof typeof statusColors;

export function StatusDot({
  variant = "idle",
  className,
  pulse = false,
}: {
  variant?: StatusDotVariant;
  className?: string;
  pulse?: boolean;
}) {
  return (
    <span className={cn("relative inline-flex size-2 shrink-0", className)}>
      {pulse && (
        <span
          className={cn(
            "absolute inline-flex size-full animate-ping rounded-full opacity-40",
            statusColors[variant]
          )}
        />
      )}
      <span
        className={cn("relative inline-flex size-2 rounded-full", statusColors[variant])}
      />
    </span>
  );
}
