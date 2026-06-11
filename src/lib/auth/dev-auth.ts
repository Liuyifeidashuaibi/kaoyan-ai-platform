import type { User } from "@supabase/supabase-js";

import { getSupabaseEnv } from "@/lib/supabase/env";

/** 本地开发且未配置 Supabase 时，跳过登录校验 */
export function shouldSkipAuthInDev() {
  return process.env.NODE_ENV === "development" && !getSupabaseEnv();
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
