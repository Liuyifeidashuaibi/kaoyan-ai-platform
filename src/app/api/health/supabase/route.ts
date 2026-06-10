import { NextResponse } from "next/server";

import { createClient } from "@/lib/supabase/server";
import { getSupabaseEnv } from "@/lib/supabase/env";

export async function GET() {
  try {
    const { url } = getSupabaseEnv();
    const supabase = await createClient();
    const { data, error } = await supabase.auth.getClaims();

    const tables: Record<string, string> = {};
    for (const table of [
      "schools",
      "majors",
      "users",
      "study_records",
      "chat_messages",
      "admission_data",
    ]) {
      const { error: tableError } = await supabase.from(table).select("id").limit(1);
      tables[table] = tableError ? tableError.message : "ok";
    }

    return NextResponse.json({
      ok: true,
      supabaseUrl: url,
      auth: {
        hasSession: Boolean(data?.claims),
        userId: data?.claims?.sub ?? null,
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
