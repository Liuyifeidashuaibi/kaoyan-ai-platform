import type { TimerPreferences } from "@/app/(main)/timer/_lib/types";
import { clampCountdownMinutes } from "@/app/(main)/timer/_lib/utils";

const STORAGE_KEY = "kaoyan-timer-preferences-v1";

const DEFAULT_PREFERENCES: TimerPreferences = {
  countdownMinutes: 25,
  dailyGoalMinutes: 240,
};

export function getTimerPreferences(): TimerPreferences {
  if (typeof window === "undefined") {
    return DEFAULT_PREFERENCES;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return DEFAULT_PREFERENCES;
    }
    const parsed = JSON.parse(raw) as Partial<TimerPreferences>;
    return {
      countdownMinutes: clampCountdownMinutes(
        parsed.countdownMinutes ?? DEFAULT_PREFERENCES.countdownMinutes
      ),
      dailyGoalMinutes: parsed.dailyGoalMinutes ?? DEFAULT_PREFERENCES.dailyGoalMinutes,
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function setTimerPreferences(next: TimerPreferences): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    return true;
  } catch {
    return false;
  }
}
