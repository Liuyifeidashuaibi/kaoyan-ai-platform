"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[app/error]", error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 p-6 text-center">
      <h2 className="text-xl font-semibold">页面加载出错</h2>
      <p className="max-w-md text-sm text-muted-foreground">
        {error.message || "发生了未知错误，请稍后重试。"}
      </p>
      <Button type="button" onClick={reset}>
        重试
      </Button>
    </div>
  );
}
