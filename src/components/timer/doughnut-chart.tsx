import type { SubjectStatItem } from "./types";
import { formatDurationEn } from "./utils";

interface DoughnutChartProps {
  items: SubjectStatItem[];
  centerTop?: string;
  centerMain: string;
  centerBottom?: string;
}

function polarToCartesian(
  cx: number,
  cy: number,
  radius: number,
  angleDeg: number
) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(rad),
    y: cy + radius * Math.sin(rad),
  };
}

function describeDonutArc(
  cx: number,
  cy: number,
  outerR: number,
  innerR: number,
  startAngle: number,
  endAngle: number
) {
  if (endAngle - startAngle >= 359.99) {
    endAngle = startAngle + 359.99;
  }

  const outerStart = polarToCartesian(cx, cy, outerR, startAngle);
  const outerEnd = polarToCartesian(cx, cy, outerR, endAngle);
  const innerStart = polarToCartesian(cx, cy, innerR, endAngle);
  const innerEnd = polarToCartesian(cx, cy, innerR, startAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;

  return [
    `M ${outerStart.x} ${outerStart.y}`,
    `A ${outerR} ${outerR} 0 ${largeArc} 1 ${outerEnd.x} ${outerEnd.y}`,
    `L ${innerStart.x} ${innerStart.y}`,
    `A ${innerR} ${innerR} 0 ${largeArc} 0 ${innerEnd.x} ${innerEnd.y}`,
    "Z",
  ].join(" ");
}

export function DoughnutChart({
  items,
  centerTop,
  centerMain,
  centerBottom,
}: DoughnutChartProps) {
  const total = items.reduce((sum, item) => sum + item.durationSeconds, 0);

  if (items.length === 0 || total <= 0) {
    return (
      <p className="py-12 text-center text-sm text-neutral-400">No data yet.</p>
    );
  }

  const size = 220;
  const cx = size / 2;
  const cy = size / 2;
  const outerR = 98;
  const innerR = 62;

  let angle = 0;
  const segments = items.map((item) => {
    const sweep = (item.durationSeconds / total) * 360;
    const start = angle;
    angle += sweep;
    return { ...item, start, end: angle };
  });

  return (
    <div className="flex flex-col items-center gap-8 sm:flex-row sm:items-center">
      <div
        className="relative shrink-0 rounded-full"
        style={{
          width: size,
          height: size,
          boxShadow:
            "0 12px 32px rgba(0,0,0,0.08), 0 2px 8px rgba(0,0,0,0.04)",
        }}
      >
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <defs>
            <filter id="donut-soft" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow
                dx="0"
                dy="2"
                stdDeviation="3"
                floodOpacity="0.12"
              />
            </filter>
          </defs>
          {segments.map((seg) => (
            <path
              key={seg.subjectId}
              d={describeDonutArc(cx, cy, outerR, innerR, seg.start, seg.end)}
              fill={seg.color}
              filter="url(#donut-soft)"
            />
          ))}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          {centerTop && (
            <p className="text-xs font-medium text-neutral-400">{centerTop}</p>
          )}
          <p className="text-xl font-semibold tabular-nums tracking-tight text-neutral-900">
            {centerMain}
          </p>
          {centerBottom && (
            <p className="mt-0.5 text-xs text-neutral-400">{centerBottom}</p>
          )}
        </div>
      </div>

      <ul className="min-w-0 flex-1 space-y-4">
        {items.map((item) => (
          <li key={item.subjectId} className="flex items-start justify-between gap-4">
            <span className="flex min-w-0 items-center gap-2.5 pt-0.5">
              <span
                className="h-0.5 w-4 shrink-0 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              <span className="truncate text-sm font-medium text-neutral-800">
                {item.name}
              </span>
            </span>
            <div className="shrink-0 text-right">
              <p className="text-sm font-medium tabular-nums text-neutral-700">
                {item.percent}%
              </p>
              <p className="text-xs tabular-nums text-neutral-400">
                {formatDurationEn(item.durationSeconds)}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
