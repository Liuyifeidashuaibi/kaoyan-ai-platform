import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";
import type { Database } from "@/types/database";
import type { TimerSession, TimerSubject } from "@/app/(main)/timer/_lib/types";

type StudySubjectRow = Database["public"]["Tables"]["study_subjects"]["Row"];
type StudySessionRow = Database["public"]["Tables"]["study_timer_sessions"]["Row"];
type StudySubjectInsert =
  Database["public"]["Tables"]["study_subjects"]["Insert"];
type StudySessionInsert =
  Database["public"]["Tables"]["study_timer_sessions"]["Insert"];

type TimerDbClient = {
  auth: ReturnType<typeof createClient>["auth"];
  from(table: "study_subjects"): {
    select: (columns: string) => {
      eq: (
        column: string,
        value: string
      ) => {
        order: (
          column: string,
          options: { ascending: boolean }
        ) => Promise<{ data: StudySubjectRow[] | null; error: { message: string } | null }>;
      };
    };
    insert: (values: StudySubjectInsert) => {
      select: (columns: string) => {
        single: () => Promise<{
          data: StudySubjectRow | null;
          error: { message: string; code?: string } | null;
        }>;
      };
    };
    delete: () => {
      eq: (
        column: string,
        value: string
      ) => Promise<{ error: { message: string } | null }>;
    };
  };
  from(table: "study_timer_sessions"): {
    select: (columns: string) => {
      eq: (
        column: string,
        value: string
      ) => {
        order: (
          column: string,
          options: { ascending: boolean }
        ) => Promise<{ data: StudySessionRow[] | null; error: { message: string } | null }>;
      };
    };
    insert: (values: StudySessionInsert) => {
      select: (columns: string) => {
        single: () => Promise<{
          data: StudySessionRow | null;
          error: { message: string } | null;
        }>;
      };
    };
  };
  rpc: (
    fn: "increment_subject_total_seconds",
    args: {
      p_subject_id: string;
      p_user_id: string;
      p_delta_seconds: number;
    }
  ) => Promise<{ error: { message: string } | null }>;
};

function getDb(): TimerDbClient {
  return createClient() as unknown as TimerDbClient;
}

const SUBJECT_COLORS = [
  "#3b82f6",
  "#6366f1",
  "#8b5cf6",
  "#0ea5e9",
  "#14b8a6",
  "#22c55e",
  "#f59e0b",
  "#ef4444",
] as const;

function mapSubject(
  row: Pick<
    StudySubjectRow,
    "id" | "name" | "color" | "total_seconds" | "created_at"
  >
): TimerSubject {
  return {
    id: row.id,
    name: row.name,
    color: row.color,
    totalSeconds: Number(row.total_seconds),
    createdAt: row.created_at,
  };
}

function mapSession(
  row: Pick<
    StudySessionRow,
    | "id"
    | "subject_id"
    | "mode"
    | "duration_seconds"
    | "started_at"
    | "ended_at"
  >,
  subjectName: string
): TimerSession {
  return {
    id: row.id,
    subjectId: row.subject_id,
    subjectName,
    mode: row.mode,
    durationSeconds: row.duration_seconds,
    startedAt: row.started_at,
    endedAt: row.ended_at,
  };
}

export function assignSubjectColor(index: number): string {
  return SUBJECT_COLORS[index % SUBJECT_COLORS.length];
}

export async function getCurrentUserId(): Promise<string | null> {
  if (!isSupabaseConfigured()) {
    return null;
  }

  const supabase = getDb();
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error || !user) {
    return null;
  }

  return user.id;
}

export async function fetchTimerData(userId: string): Promise<{
  subjects: TimerSubject[];
  sessions: TimerSession[];
}> {
  const supabase = getDb();

  const [subjectsResult, sessionsResult] = await Promise.all([
    supabase
      .from("study_subjects")
      .select("id, name, color, total_seconds, created_at")
      .eq("user_id", userId)
      .order("created_at", { ascending: true }),
    supabase
      .from("study_timer_sessions")
      .select("id, subject_id, mode, duration_seconds, started_at, ended_at")
      .eq("user_id", userId)
      .order("started_at", { ascending: false }),
  ]);

  if (subjectsResult.error) {
    throw new Error(subjectsResult.error.message);
  }
  if (sessionsResult.error) {
    throw new Error(sessionsResult.error.message);
  }

  const subjects = (subjectsResult.data ?? []).map(mapSubject);
  const subjectNameMap = new Map(subjects.map((s) => [s.id, s.name]));

  const sessions = (sessionsResult.data ?? []).map((row) =>
    mapSession(row, subjectNameMap.get(row.subject_id) ?? "未知科目")
  );

  return { subjects, sessions };
}

export async function createSubject(
  userId: string,
  name: string,
  existingCount: number
): Promise<TimerSubject> {
  const trimmed = name.trim();
  if (trimmed.length < 1 || trimmed.length > 20) {
    throw new Error("科目名称需为 1-20 个字符");
  }

  const supabase = getDb();
  const insertPayload: StudySubjectInsert = {
    user_id: userId,
    name: trimmed,
    color: assignSubjectColor(existingCount),
    total_seconds: 0,
  };
  const { data, error } = await supabase
    .from("study_subjects")
    .insert(insertPayload)
    .select("id, name, color, total_seconds, created_at")
    .single();

  if (error) {
    if (error.code === "23505") {
      throw new Error("该科目已存在");
    }
    throw new Error(error.message);
  }

  if (!data) {
    throw new Error("创建科目失败");
  }

  return mapSubject(data);
}

export async function deleteSubject(subjectId: string): Promise<void> {
  const supabase = getDb();
  const { error } = await supabase
    .from("study_subjects")
    .delete()
    .eq("id", subjectId);

  if (error) {
    throw new Error(error.message);
  }
}

export async function saveTimerSession(payload: {
  userId: string;
  subjectId: string;
  mode: "stopwatch" | "countdown";
  durationSeconds: number;
  startedAt: string;
  endedAt: string;
}): Promise<TimerSession> {
  if (payload.durationSeconds <= 0) {
    throw new Error("学习时长需大于 0 秒");
  }

  const supabase = getDb();
  const insertPayload: StudySessionInsert = {
    user_id: payload.userId,
    subject_id: payload.subjectId,
    mode: payload.mode,
    duration_seconds: payload.durationSeconds,
    started_at: payload.startedAt,
    ended_at: payload.endedAt,
  };

  const { data, error } = await supabase
    .from("study_timer_sessions")
    .insert(insertPayload)
    .select("id, subject_id, mode, duration_seconds, started_at, ended_at")
    .single();

  if (error) {
    throw new Error(error.message);
  }

  const { error: rpcError } = await supabase.rpc(
    "increment_subject_total_seconds",
    {
      p_subject_id: payload.subjectId,
      p_user_id: payload.userId,
      p_delta_seconds: payload.durationSeconds,
    }
  );

  if (rpcError) {
    throw new Error(rpcError.message);
  }

  if (!data) {
    throw new Error("保存番茄钟记录失败");
  }

  return mapSession(data, "");
}
