import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { getLoginErrorMessage, safeNextPath } from "@/lib/auth/navigation";
import { getSupabaseEnv } from "@/lib/supabase/env";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = safeNextPath(searchParams.get("next"));

  if (!code) {
    return NextResponse.redirect(`${origin}/login?error=auth_callback_failed`);
  }

  const env = getSupabaseEnv();
  if (!env) {
    console.error("[auth/callback] Missing Supabase environment variables");
    return NextResponse.redirect(`${origin}/login?error=config_missing`);
  }

  const cookieStore = await cookies();
  const redirectUrl = new URL(next, origin);
  let response = NextResponse.redirect(redirectUrl);

  const supabase = createServerClient(env.url, env.key, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet, headers) {
        cookiesToSet.forEach(({ name, value, options }) => {
          cookieStore.set(name, value, options);
          response.cookies.set(name, value, options);
        });
        if (headers) {
          Object.entries(headers).forEach(([headerKey, headerValue]) => {
            response.headers.set(headerKey, headerValue);
          });
        }
      },
    },
  });

  const { error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    console.error(
      "[auth/callback] exchangeCodeForSession failed:",
      error.message
    );
    return NextResponse.redirect(`${origin}/login?error=auth_callback_failed`);
  }

  return response;
}
