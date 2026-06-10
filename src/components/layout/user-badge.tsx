"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { createClient } from "@/lib/supabase/client";

export function UserBadge() {
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();

    supabase.auth.getUser().then(({ data: { user } }) => {
      setEmail(user?.email ?? null);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setEmail(session?.user?.email ?? null);
    });

    return () => subscription.unsubscribe();
  }, []);

  if (!email) {
    return (
      <Link
        href="/login"
        className="text-sm font-medium text-muted-foreground hover:text-foreground"
      >
        登录
      </Link>
    );
  }

  return (
    <span className="max-w-[180px] truncate text-sm text-muted-foreground">
      {email}
    </span>
  );
}
