import { NextResponse } from "next/server";

import { createClient } from "@/lib/supabase/server";
import { getSupabaseEnv } from "@/lib/supabase/env";

export async function GET() {
  if (process.env.NODE_ENV === "production") {
    return NextResponse.json({ ok: true });
  }

  try {
    const env = getSupabaseEnv();
    if (!env) {
      return NextResponse.json(
        {
          ok: false,
          error:
            "Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY",
        },
        { status: 500 }
      );
    }

    const supabase = await createClient();
    const { data } = await supabase.auth.getClaims();

    const tables: Record<string, string> = {};
    for (const table of [
      "schools",
      "majors",
      "users",
      "study_records",
      "chat_messages",
      "admission_data",
    ]) {
      const { error: tableError } = await supabase
        .from(table)
        .select("id")
        .limit(1);
      tables[table] = tableError ? tableError.message : "ok";
    }

    return NextResponse.json({
      ok: true,
      auth: {
        hasSession: Boolean(data?.claims),
      },
      tables,
    });
  } catch (error) {
    return NextResponse.json(
      {
        ok: false,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}
