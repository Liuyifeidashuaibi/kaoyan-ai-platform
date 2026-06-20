import { cn } from "@/lib/utils";

type MetricCardProps = {
  label: string;
  value: string | number;
  delta?: string;
  deltaTrend?: "up" | "down" | "neutral";
  href?: string;
  className?: string;
};

export function MetricCard({
  label,
  value,
  delta,
  deltaTrend = "neutral",
  className,
}: MetricCardProps) {
  const trendClass =
    deltaTrend === "up"
      ? "text-emerald-600"
      : deltaTrend === "down"
        ? "text-red-600"
        : "text-muted-foreground";

  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-xl border border-border/60 bg-card px-5 py-4",
        className
      )}
    >
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-3xl font-medium tracking-tight tabular-nums text-foreground">
        {value}
      </span>
      {delta ? (
        <span className={cn("text-xs", trendClass)}>{delta}</span>
      ) : (
        <span className="text-xs text-transparent select-none">—</span>
      )}
    </div>
  );
}
