import type {
  BarChartItem,
  StatsPeriod,
  StudyRecord,
  Subject,
  TomatoStatsSummary,
  TomatoStorage,
} from "@/components/TomatoClock/types";

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

export function toDateKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
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

export function filterRecordsByPeriod(
  records: StudyRecord[],
  period: StatsPeriod,
  now = new Date()
): StudyRecord[] {
  const start = getPeriodStart(period, now);
  if (!start) {
    return records;
  }
  const startMs = start.getTime();
  return records.filter(
    (record) => new Date(record.completedAt).getTime() >= startMs
  );
}

function computeSubjectDurations(
  records: StudyRecord[],
  subjects: Subject[]
): Map<string, number> {
  const map = new Map<string, number>();
  subjects.forEach((subject) => map.set(subject.id, 0));
  records.forEach((record) => {
    map.set(
      record.subjectId,
      (map.get(record.subjectId) ?? 0) + record.durationSeconds
    );
  });
  return map;
}

export function buildBarChartItems(
  subjects: Subject[],
  durationMap: Map<string, number>,
  includeEmpty = true
): BarChartItem[] {
  const sorted = [...subjects].sort((a, b) => a.sortOrder - b.sortOrder);
  const maxSeconds = sorted.reduce(
    (max, subject) => Math.max(max, durationMap.get(subject.id) ?? 0),
    0
  );

  const items = sorted.map((subject) => {
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

  return includeEmpty
    ? items
    : items.filter((item) => item.durationSeconds > 0);
}

export function computeStatsSummary(
  storage: TomatoStorage,
  period: StatsPeriod = "today"
): TomatoStatsSummary {
  const filtered = filterRecordsByPeriod(storage.records, period);
  const totalSeconds = filtered.reduce(
    (sum, record) => sum + record.durationSeconds,
    0
  );
  const dailyGoalSeconds = storage.dailyGoalMinutes * 60;
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
  const durationMap = computeSubjectDurations(filtered, storage.subjects);

  return {
    period,
    totalSeconds,
    formattedTotal: formatHourMinute(totalSeconds),
    goalPercent,
    dailyGoalSeconds: goalSeconds,
    barItems: buildBarChartItems(storage.subjects, durationMap, true),
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
