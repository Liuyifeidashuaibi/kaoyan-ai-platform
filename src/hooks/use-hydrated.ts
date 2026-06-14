"use client";

import { useEffect, useState } from "react";

/** 客户端 hydration 完成后再返回 true，避免 SSR 与首屏 DOM 不一致。 */
export function useHydrated(): boolean {
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  return hydrated;
}
