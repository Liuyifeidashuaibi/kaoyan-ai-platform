"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { createClient } from "@/lib/supabase/client";

export function AdminUserBadge() {
  const [label, setLabel] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(({ data }) => {
      const email = data.session?.user?.email;
      if (email) {
        setLabel(email);
        return;
      }
      if (process.env.NEXT_PUBLIC_SKIP_AUTH_IN_DEV === "true") {
        setLabel("dev@local");
      }
    });
  }, []);

  const initial = label ? label.charAt(0).toUpperCase() : "?";

  return (
    <Link
      href="/profile"
      className="flex max-w-[140px] items-center gap-2 rounded-full bg-muted py-1 pl-1 pr-2.5 text-xs text-muted-foreground transition-colors hover:bg-muted/80 hover:text-foreground"
      title={label ?? "未登录"}
    >
      <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-background text-[11px] font-medium">
        {initial}
      </span>
      <span className="truncate">{label ?? "…"}</span>
    </Link>
  );
}
