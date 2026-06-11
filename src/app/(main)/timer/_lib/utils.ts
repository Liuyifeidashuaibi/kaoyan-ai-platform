import type {
  BarChartItem,
  StatsPeriod,
  TimerSession,
  TimerSubject,
  TimerStatsSummary,
} from "@/app/(main)/timer/_lib/types";

export function formatMmSs(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function formatHourMinute(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  return `${hours}:${String(minutes).padStart(2, "0")}`;
}

function startOfDay(date: Date): Date {
  const next = new Date(date);
  next.setHours(0, 0, 0, 0);
  return next;
}

function startOfWeek(date: Date): Date {
  const next = startOfDay(date);
  const day = next.getDay();
  const diff = day === 0 ? 6 : day - 1;
  next.setDate(next.getDate() - diff);
  return next;
}

function startOfMonth(date: Date): Date {
  const next = startOfDay(date);
  next.setDate(1);
  return next;
}

export function getPeriodStart(
  period: StatsPeriod,
  now = new Date()
): Date | null {
  switch (period) {
    case "today":
      return startOfDay(now);
    case "week":
      return startOfWeek(now);
    case "month":
      return startOfMonth(now);
    case "all":
      return null;
  }
}

export function filterSessionsByPeriod(
  sessions: TimerSession[],
  period: StatsPeriod,
  now = new Date()
): TimerSession[] {
  const start = getPeriodStart(period, now);
  if (!start) {
    return sessions;
  }
  const startMs = start.getTime();
  return sessions.filter(
    (session) => new Date(session.startedAt).getTime() >= startMs
  );
}

function computeSubjectDurations(
  sessions: TimerSession[],
  subjects: TimerSubject[]
): Map<string, number> {
  const map = new Map<string, number>();
  subjects.forEach((subject) => map.set(subject.id, 0));
  sessions.forEach((session) => {
    map.set(
      session.subjectId,
      (map.get(session.subjectId) ?? 0) + session.durationSeconds
    );
  });
  return map;
}

export function buildBarChartItems(
  subjects: TimerSubject[],
  durationMap: Map<string, number>
): BarChartItem[] {
  const sorted = [...subjects].sort(
    (a, b) =>
      new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
  );
  const maxSeconds = sorted.reduce(
    (max, subject) => Math.max(max, durationMap.get(subject.id) ?? 0),
    0
  );

  return sorted.map((subject) => {
    const durationSeconds = durationMap.get(subject.id) ?? 0;
    return {
      subjectId: subject.id,
      name: subject.name,
      color: subject.color,
      durationSeconds,
      barPercent:
        maxSeconds > 0
          ? Math.round((durationSeconds / maxSeconds) * 100)
          : 0,
      formattedDuration: formatHourMinute(durationSeconds),
    };
  });
}

export function computeStatsSummary(
  subjects: TimerSubject[],
  sessions: TimerSession[],
  period: StatsPeriod,
  dailyGoalMinutes: number
): TimerStatsSummary {
  const filtered = filterSessionsByPeriod(sessions, period);
  const totalSeconds = filtered.reduce(
    (sum, session) => sum + session.durationSeconds,
    0
  );
  const dailyGoalSeconds = dailyGoalMinutes * 60;
  const periodGoalMultiplier =
    period === "today"
      ? 1
      : period === "week"
        ? 7
        : period === "month"
          ? 30
          : 30;
  const goalSeconds = dailyGoalSeconds * periodGoalMultiplier;
  const goalPercent = Math.min(
    100,
    Math.round((totalSeconds / Math.max(goalSeconds, 1)) * 100)
  );
  const durationMap = computeSubjectDurations(filtered, subjects);

  return {
    period,
    totalSeconds,
    formattedTotal: formatHourMinute(totalSeconds),
    goalPercent,
    goalSeconds,
    barItems: buildBarChartItems(subjects, durationMap),
  };
}

export function getPeriodLabel(period: StatsPeriod): string {
  switch (period) {
    case "today":
      return "今日";
    case "week":
      return "本周";
    case "month":
      return "本月";
    case "all":
      return "总计";
  }
}

export function clampCountdownMinutes(value: number): number {
  return Math.min(60, Math.max(5, Math.round(value)));
}
