import { SUBJECT_COLOR_PALETTE } from "@/lib/study-timer/constants";

/** 根据已有科目数量分配下一个标识色 */
export function assignSubjectColor(existingSubjectCount: number): string {
  const index = existingSubjectCount % SUBJECT_COLOR_PALETTE.length;
  return SUBJECT_COLOR_PALETTE[index] ?? SUBJECT_COLOR_PALETTE[0];
}

/** 校验并规范化科目名称 */
export function normalizeSubjectName(raw: string): string {
  return raw.trim().replace(/\s+/g, " ");
}

/** 校验科目名称是否合法 */
export function isValidSubjectName(name: string, maxLength: number): boolean {
  const normalized = normalizeSubjectName(name);
  return normalized.length >= 1 && normalized.length <= maxLength;
}

/** 生成客户端 UUID */
export function createClientId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `local-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

/** 将分钟转为秒 */
export function minutesToSeconds(minutes: number): number {
  return Math.round(minutes * 60);
}

/** 将秒格式化为 时/分 展示文案 */
export function formatDurationZh(totalSeconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);

  if (hours > 0 && minutes > 0) {
    return `${hours}小时${minutes}分钟`;
  }
  if (hours > 0) {
    return `${hours}小时`;
  }
  if (minutes > 0) {
    return `${minutes}分钟`;
  }
  return "0分钟";
}

/** 将秒格式化为 HH:MM:SS 计时器展示 */
export function formatClockTime(totalSeconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const seconds = safeSeconds % 60;

  return [hours, minutes, seconds]
    .map((value) => String(value).padStart(2, "0"))
    .join(":");
}

/** 计算各科目时长占比 */
export function calculatePercentage(
  subjectSeconds: number,
  totalSeconds: number
): number {
  if (totalSeconds <= 0) {
    return 0;
  }
  return Math.round((subjectSeconds / totalSeconds) * 1000) / 10;
}
