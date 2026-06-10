import { formatClockTime } from "@/lib/study-timer/utils";

interface TimerDisplayProps {
  label: string;
  seconds: number;
  accentColor: string;
}

export function TimerDisplay({ label, seconds, accentColor }: TimerDisplayProps) {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-2xl border border-border bg-muted/30 px-6 py-12"
      style={{ boxShadow: `inset 0 0 0 1px ${accentColor}22` }}
    >
      <p className="mb-4 text-sm text-muted-foreground">{label}</p>
      <p
        className="font-mono text-5xl font-semibold tracking-wider tabular-nums sm:text-6xl"
        style={{ color: accentColor }}
      >
        {formatClockTime(seconds)}
      </p>
    </div>
  );
}
