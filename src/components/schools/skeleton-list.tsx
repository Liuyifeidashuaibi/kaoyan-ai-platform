import { cn } from "@/lib/utils";

interface SkeletonListProps {
  count?: number;
  className?: string;
}

function SkeletonBlock({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-muted",
        className
      )}
    />
  );
}

export function SkeletonUniversityCard() {
  return (
    <div className="flex items-center gap-3 p-4 border-b border-border last:border-0">
      <SkeletonBlock className="size-12 shrink-0 rounded-full" />
      <div className="flex-1 min-w-0 space-y-2">
        <SkeletonBlock className="h-4 w-32" />
        <SkeletonBlock className="h-3 w-48" />
        <SkeletonBlock className="h-3 w-24" />
      </div>
    </div>
  );
}

export function SkeletonList({ count = 8, className }: SkeletonListProps) {
  return (
    <div className={cn("bg-card rounded-xl overflow-hidden", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonUniversityCard key={i} />
      ))}
    </div>
  );
}

export function SkeletonScoreRow() {
  return (
    <div className="flex gap-3 py-3 border-b border-border last:border-0">
      <SkeletonBlock className="h-4 w-24" />
      <SkeletonBlock className="h-4 w-12" />
      <SkeletonBlock className="h-4 w-12" />
      <SkeletonBlock className="h-4 w-12" />
      <SkeletonBlock className="h-4 w-12" />
    </div>
  );
}

export function SkeletonDetail() {
  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center gap-4">
        <SkeletonBlock className="size-20 rounded-full" />
        <div className="space-y-2">
          <SkeletonBlock className="h-5 w-40" />
          <SkeletonBlock className="h-4 w-56" />
        </div>
      </div>
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonBlock key={i} className="h-4 w-full" />
        ))}
      </div>
    </div>
  );
}
