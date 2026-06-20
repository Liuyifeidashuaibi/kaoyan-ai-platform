import { apiFetch } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";

function shouldUseDevAdminToken(): boolean {
  if (process.env.NODE_ENV !== "development") return false;
  return (
    process.env.NEXT_PUBLIC_SKIP_AUTH_IN_DEV === "true" ||
    process.env.SKIP_AUTH_IN_DEV === "true"
  );
}

async function adminAuthHeaders(): Promise<HeadersInit> {
  try {
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) {
      return { Authorization: `Bearer ${token}` };
    }
  } catch {
    /* no session */
  }
  if (shouldUseDevAdminToken()) {
    return { Authorization: "Bearer dev" };
  }
  return {};
}

export async function adminFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const headers = await adminAuthHeaders();
  return apiFetch<T>(path, {
    ...init,
    headers: {
      ...headers,
      ...(init?.headers ?? {}),
    },
  });
}
