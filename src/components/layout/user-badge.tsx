"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { shouldSkipAuthInDev } from "@/lib/auth/dev-auth";
import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";

export function UserBadge() {
  const [email, setEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isSupabaseConfigured()) {
      if (shouldSkipAuthInDev()) {
        setEmail("开发模式");
      }
      setLoading(false);
      return;
    }

    let subscription: { unsubscribe: () => void } | undefined;

    try {
      const supabase = createClient();

      supabase.auth
        .getUser()
        .then(({ data: { user } }) => {
          setEmail(user?.email ?? null);
        })
        .catch(() => {
          setEmail(null);
        })
        .finally(() => {
          setLoading(false);
        });

      const { data } = supabase.auth.onAuthStateChange((_event, session) => {
        setEmail(session?.user?.email ?? null);
        setLoading(false);
      });

      subscription = data.subscription;
    } catch {
      setLoading(false);
    }

    return () => subscription?.unsubscribe();
  }, []);

  if (loading) {
    return (
      <span className="text-sm text-muted-foreground" aria-hidden>
        ···
      </span>
    );
  }

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
    <span
      className="max-w-[180px] truncate text-sm text-muted-foreground"
      title={email}
    >
      {email}
    </span>
  );
}
