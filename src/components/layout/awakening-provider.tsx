"use client";

/**
 * AwakeningProvider — shows TheAwakeningLoader once per browser session.
 *
 * On subsequent navigations within the same tab the experience is skipped;
 * the user returns to the full brand reveal on a fresh tab / hard reload.
 */

import { useEffect, useState } from "react";
import { TheAwakeningLoader } from "@/components/TheAwakeningLoader";

const SESSION_KEY = "kaoyan_awakened";

export function AwakeningProvider({ children }: { children: React.ReactNode }) {
  // Start as "show" so there's no flash of content before we've checked storage.
  const [show, setShow] = useState(true);

  useEffect(() => {
    if (sessionStorage.getItem(SESSION_KEY) === "1") {
      setShow(false);
    }
  }, []);

  const handleComplete = () => {
    sessionStorage.setItem(SESSION_KEY, "1");
    setShow(false);
  };

  return (
    <>
      {show && <TheAwakeningLoader onComplete={handleComplete} />}
      {children}
    </>
  );
}
