import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";
import { shouldSkipAuthInDev } from "@/lib/auth/dev-auth";

/** 获取带 Bearer Token 的请求头（开发环境无 Supabase 时使用 dev token） */
export async function getAuthHeaders(): Promise<HeadersInit> {
  if (shouldSkipAuthInDev()) {
    return { Authorization: "Bearer dev" };
  }

  if (!isSupabaseConfigured()) {
    return {};
  }

  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (session?.access_token) {
    return { Authorization: `Bearer ${session.access_token}` };
  }
  return {};
}
