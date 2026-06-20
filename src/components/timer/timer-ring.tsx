interface TimerRingProps {
  progress: number;
  color?: string;
  children: React.ReactNode;
}

const VIEW_SIZE = 260;
const STROKE = 10;
const RADIUS = (VIEW_SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function TimerRing({
  progress,
  color = "#93C5FD",
  children,
}: TimerRingProps) {
  const clamped = Math.min(1, Math.max(0, progress));
  const offset = CIRCUMFERENCE * (1 - clamped);

  return (
    <div className="relative mx-auto aspect-square w-[min(220px,calc(100vw-3rem))] max-w-[260px]">
      <svg
        viewBox={`0 0 ${VIEW_SIZE} ${VIEW_SIZE}`}
        className="size-full -rotate-90"
        aria-hidden
      >
        <circle
          cx={VIEW_SIZE / 2}
          cy={VIEW_SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke="#F3F4F6"
          strokeWidth={STROKE}
        />
        <circle
          cx={VIEW_SIZE / 2}
          cy={VIEW_SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke={color}
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          className="transition-[stroke-dashoffset] duration-300 ease-linear"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center px-4 text-center">
        {children}
      </div>
    </div>
  );
}
