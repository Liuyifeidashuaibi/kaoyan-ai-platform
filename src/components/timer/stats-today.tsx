import type { SubjectStatItem } from "./types";
import { formatDurationEn } from "./utils";

interface StatsTodayProps {
  items: SubjectStatItem[];
}

export function StatsToday({ items }: StatsTodayProps) {
  if (items.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-neutral-400">
        No study records for today.
      </p>
    );
  }

  return (
    <ul className="space-y-6">
      {items.map((item) => (
        <li key={item.subjectId}>
          <div className="mb-2.5 flex items-baseline justify-between gap-3">
            <span className="text-[15px] font-semibold text-neutral-900">
              {item.name}
            </span>
            <span className="text-sm font-medium tabular-nums text-neutral-500">
              {formatDurationEn(item.durationSeconds)}
            </span>
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-neutral-100">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${item.barPercent}%`,
                backgroundColor: item.color,
              }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
