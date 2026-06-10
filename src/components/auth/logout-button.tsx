"use client";

import { useState, useTransition } from "react";

import { signOut } from "@/app/actions/auth";
import { Button } from "@/components/ui/button";

export function LogoutButton() {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="flex flex-col items-end gap-2">
      <Button
        type="button"
        variant="outline"
        disabled={pending}
        onClick={() => {
          setError(null);
          startTransition(async () => {
            try {
              await signOut();
            } catch (signOutError) {
              setError(
                signOutError instanceof Error
                  ? signOutError.message
                  : "退出失败，请重试。"
              );
            }
          });
        }}
      >
        {pending ? "退出中..." : "退出登录"}
      </Button>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  );
}
