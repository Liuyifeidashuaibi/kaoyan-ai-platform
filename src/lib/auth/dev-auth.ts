import type { User } from "@supabase/supabase-js";

import { getSupabaseEnv } from "@/lib/supabase/env";

/** 本地开发跳过登录：未配置 Supabase，或显式设置 SKIP_AUTH_IN_DEV=true */
export function shouldSkipAuthInDev() {
  if (process.env.NODE_ENV !== "development") return false;

  const explicitSkip =
    process.env.SKIP_AUTH_IN_DEV === "true" ||
    process.env.NEXT_PUBLIC_SKIP_AUTH_IN_DEV === "true";

  if (explicitSkip) return true;

  return !getSupabaseEnv();
}

export function createDevUser(): User {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    aud: "authenticated",
    role: "authenticated",
    email: "dev@local.test",
    created_at: new Date(0).toISOString(),
    app_metadata: {},
    user_metadata: {},
  };
}
