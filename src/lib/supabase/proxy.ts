import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { isAuthRoute, isProtectedRoute } from "@/config/auth";
import { getSupabaseEnv } from "@/lib/supabase/env";

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

    const { data, error } = await supabase.auth.getClaims();

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
