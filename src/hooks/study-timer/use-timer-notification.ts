"use client";

import { useCallback, useEffect, useState } from "react";

import { NOTIFICATION_REQUEST_DELAY_MS } from "@/lib/study-timer/constants";

export function useTimerNotification() {
  const [permission, setPermission] = useState<NotificationPermission>("default");

  useEffect(() => {
    if (typeof window === "undefined" || !("Notification" in window)) {
      return;
    }
    setPermission(Notification.permission);
  }, []);

  const requestPermission = useCallback(async () => {
    if (typeof window === "undefined" || !("Notification" in window)) {
      return;
    }

    if (Notification.permission === "granted") {
      setPermission("granted");
      return;
    }

    if (Notification.permission !== "denied") {
      const result = await Notification.requestPermission();
      setPermission(result);
    }
  }, []);

  const notifyComplete = useCallback((subjectName: string) => {
    if (typeof window === "undefined" || !("Notification" in window)) {
      return;
    }

    if (Notification.permission === "granted") {
      new Notification("计时完成", {
        body: `${subjectName} 倒计时已结束，辛苦了！`,
        tag: "study-timer-complete",
      });
    }
  }, []);

  /** 首次进入计时页时延迟请求通知权限 */
  useEffect(() => {
    const timerId = window.setTimeout(() => {
      void requestPermission();
    }, NOTIFICATION_REQUEST_DELAY_MS);

    return () => window.clearTimeout(timerId);
  }, [requestPermission]);

  return { permission, notifyComplete };
}
