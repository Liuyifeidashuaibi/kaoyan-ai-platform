"use client";

import { useTransition } from "react";

import { signOut } from "@/app/actions/auth";
import { Button } from "@/components/ui/button";

export function LogoutButton() {
  const [pending, startTransition] = useTransition();

  return (
    <Button
      type="button"
      variant="outline"
      disabled={pending}
      onClick={() => startTransition(() => signOut())}
    >
      {pending ? "退出中..." : "退出登录"}
    </Button>
  );
}
