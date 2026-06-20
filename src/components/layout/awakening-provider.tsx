"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { TheAwakeningLoader } from "@/components/TheAwakeningLoader";

const SESSION_KEY = "kaoyan_awakened";

export function AwakeningProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isAdmin = pathname.startsWith("/admin");
  const [show, setShow] = useState(!isAdmin);

  useEffect(() => {
    if (isAdmin) {
      setShow(false);
      return;
    }
    if (sessionStorage.getItem(SESSION_KEY) === "1") {
      setShow(false);
    }
  }, [isAdmin]);

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
