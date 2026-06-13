/**
 * 择校模块数据同步：爬虫写库后 bump revision，前端检测变化并刷新缓存
 */
import { createClient } from "@/lib/supabase/client";
import { invalidateSchoolsCache } from "@/lib/api/schools";

/** 轮询间隔（毫秒） */
export const SCHOOLS_SYNC_POLL_MS = 30_000;

export type SchoolsSyncMeta = {
  revision: number;
  updated_at: string;
  note: string | null;
};

/** 读取当前数据版本（schools_sync_meta 表） */
export async function fetchSchoolsSyncMeta(): Promise<SchoolsSyncMeta | null> {
  try {
    const client = createClient();
    const { data, error } = await client
      .from("schools_sync_meta")
      .select("revision, updated_at, note")
      .eq("id", 1)
      .maybeSingle();
    if (error || !data) return null;
    return data as SchoolsSyncMeta;
  } catch {
    return null;
  }
}

/**
 * 指纹兜底：无 sync_meta 表时根据核心表最新时间判断是否有新数据
 */
export async function fetchSchoolsDataFingerprint(): Promise<string> {
  try {
    const client = createClient();
    const [maj, sco, meta] = await Promise.all([
      client
        .from("majors")
        .select("updated_at")
        .order("updated_at", { ascending: false })
        .limit(1)
        .maybeSingle(),
      client
        .from("scores")
        .select("created_at")
        .order("created_at", { ascending: false })
        .limit(1)
        .maybeSingle(),
      client
        .from("schools_sync_meta")
        .select("updated_at")
        .eq("id", 1)
        .maybeSingle(),
    ]);
    const majTs = (maj.data as { updated_at?: string } | null)?.updated_at ?? "";
    const scoTs = (sco.data as { created_at?: string } | null)?.created_at ?? "";
    const metaTs = (meta.data as { updated_at?: string } | null)?.updated_at ?? "";
    return [metaTs, majTs, scoTs].join("|");
  } catch {
    return "";
  }
}

/** 使前端缓存失效并返回新同步标记（供手动刷新） */
export function triggerSchoolsDataRefresh(): number {
  invalidateSchoolsCache();
  return Date.now();
}
