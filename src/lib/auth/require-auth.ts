import { redirect } from "next/navigation";

import { createDevUser, shouldSkipAuthInDev } from "@/lib/auth/dev-auth";
import { createClient } from "@/lib/supabase/server";

export async function requireAuth(returnPath: string) {
  if (shouldSkipAuthInDev()) {
    return createDevUser();
  }

  const supabase = await createClient();
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error || !user) {
    redirect(`/login?next=${encodeURIComponent(returnPath)}`);
  }

  return user;
}
