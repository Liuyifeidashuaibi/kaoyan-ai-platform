import type { StatsPeriod, SubjectStatItem, TimerSession, TimerSubject } from "./types";

export function formatMmSs(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function formatDurationEn(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);

  if (hours > 0 && minutes > 0) return `${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h`;
  if (minutes > 0) return `${minutes}m`;
  return "0m";
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
  if (!start) return sessions;
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

function distributePercents(durations: number[]): number[] {
  const total = durations.reduce((sum, value) => sum + value, 0);
  if (total <= 0) return durations.map(() => 0);

  const raw = durations.map((value) => (value / total) * 100);
  const rounded = raw.map((value) => Math.round(value));
  const diff = 100 - rounded.reduce((sum, value) => sum + value, 0);

  if (diff !== 0) {
    const maxIndex = durations.indexOf(Math.max(...durations));
    rounded[maxIndex] += diff;
  }

  return rounded;
}

export function buildSubjectStats(
  subjects: TimerSubject[],
  sessions: TimerSession[],
  period: StatsPeriod,
  includePercents: boolean
): SubjectStatItem[] {
  const filtered = filterSessionsByPeriod(sessions, period);
  const durationMap = computeSubjectDurations(filtered, subjects);
  const sorted = [...subjects].sort(
    (a, b) =>
      new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
  );

  const items = sorted
    .map((subject) => ({
      subjectId: subject.id,
      name: subject.name,
      color: subject.color,
      durationSeconds: durationMap.get(subject.id) ?? 0,
      barPercent: 0,
      percent: 0,
    }))
    .filter((item) => item.durationSeconds > 0)
    .sort((a, b) => b.durationSeconds - a.durationSeconds);

  const maxSeconds = items.reduce(
    (max, item) => Math.max(max, item.durationSeconds),
    0
  );

  const percents = includePercents
    ? distributePercents(items.map((item) => item.durationSeconds))
    : [];

  return items.map((item, index) => ({
    ...item,
    barPercent:
      maxSeconds > 0
        ? Math.round((item.durationSeconds / maxSeconds) * 100)
        : 0,
    percent: includePercents ? percents[index] : 0,
  }));
}

export function buildConicGradient(
  items: Pick<SubjectStatItem, "color" | "percent">[]
): string {
  if (items.length === 0) return "conic-gradient(#e5e5e5 0% 100%)";

  let acc = 0;
  const stops = items.map((item) => {
    const start = acc;
    acc += item.percent;
    return `${item.color} ${start}% ${acc}%`;
  });

  return `conic-gradient(${stops.join(", ")})`;
}

export function clampCountdownMinutes(value: number): number {
  return Math.min(180, Math.max(1, Math.round(value)));
}
