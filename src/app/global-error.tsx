"use client";

import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="zh-CN">
      <body className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
        <h2 className="text-xl font-semibold">应用出现严重错误</h2>
        <p className="max-w-md text-sm text-muted-foreground">
          {error.message || "请刷新页面或稍后再试。"}
        </p>
        <Button type="button" onClick={reset}>
          重新加载
        </Button>
      </body>
    </html>
  );
}
