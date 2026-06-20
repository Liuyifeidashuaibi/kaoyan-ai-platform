import { cn } from "@/lib/utils";

const labels = { low: "低", medium: "中", high: "高" } as const;

export function RiskBadge({
  level,
  className,
}: {
  level: "low" | "medium" | "high";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        level === "low" && "bg-emerald-500/10 text-emerald-700",
        level === "medium" && "bg-amber-500/10 text-amber-700",
        level === "high" && "bg-red-500/10 text-red-700",
        className
      )}
    >
      风险 {labels[level]}
    </span>
  );
}
