import { createServerClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";

import { isAuthRoute, isProtectedRoute } from "@/config/auth";
import { shouldSkipAuthInDev } from "@/lib/auth/dev-auth";
import { getSupabaseEnv } from "@/lib/supabase/env";

const DEV_AUTH_TIMEOUT_MS = 3000;

async function getClaimsWithDevTimeout(supabase: SupabaseClient) {
  const claimsPromise = supabase.auth.getClaims();

  if (process.env.NODE_ENV !== "development") {
    return claimsPromise;
  }

  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeoutPromise = new Promise<never>((_, reject) => {
    timer = setTimeout(
      () => reject(new Error("Supabase auth timeout")),
      DEV_AUTH_TIMEOUT_MS
    );
  });

  try {
    return await Promise.race([claimsPromise, timeoutPromise]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function redirectToLogin(request: NextRequest, pathname: string) {
  const redirectUrl = request.nextUrl.clone();
  redirectUrl.pathname = "/login";
  redirectUrl.searchParams.set("next", pathname);
  return NextResponse.redirect(redirectUrl);
}

function redirectWithCookies(url: URL, supabaseResponse: NextResponse) {
  const response = NextResponse.redirect(url);
  supabaseResponse.cookies.getAll().forEach(({ name, value }) => {
    response.cookies.set(name, value);
  });
  return response;
}

export async function updateSession(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  if (shouldSkipAuthInDev()) {
    return NextResponse.next({ request });
  }

  try {
    const env = getSupabaseEnv();

    if (!env) {

      console.error(
        "[proxy] Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY"
      );

      if (isProtectedRoute(pathname)) {
        return redirectToLogin(request, pathname);
      }

      return NextResponse.next({ request });
    }

    let supabaseResponse = NextResponse.next({ request });

    const supabase = createServerClient(env.url, env.key, {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet, headers) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          );
          if (headers) {
            Object.entries(headers).forEach(([headerKey, headerValue]) => {
              supabaseResponse.headers.set(headerKey, headerValue);
            });
          }
        },
      },
    });

    const claimsResult = await getClaimsWithDevTimeout(supabase);
    const { data, error } = claimsResult;

    if (error) {
      console.error("[proxy] getClaims failed:", error.message);
    }

    const user = data?.claims;

    if (!user && isProtectedRoute(pathname)) {
      return redirectWithCookies(
        new URL(
          `/login?next=${encodeURIComponent(pathname)}`,
          request.url
        ),
        supabaseResponse
      );
    }

    if (user && isAuthRoute(pathname)) {
      const redirectUrl = request.nextUrl.clone();
      redirectUrl.pathname = "/";
      redirectUrl.search = "";
      return redirectWithCookies(redirectUrl, supabaseResponse);
    }

    return supabaseResponse;
  } catch (error) {
    console.error("[proxy] session update failed:", error);

    if (isProtectedRoute(pathname)) {
      return redirectToLogin(request, pathname);
    }

    return NextResponse.next({ request });
  }
}
