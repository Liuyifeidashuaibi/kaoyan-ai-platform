import type { SupabaseClient } from "@supabase/supabase-js";

import {
  SUBJECT_NAME_MAX_LENGTH,
} from "@/lib/study-timer/constants";
import {
  assignSubjectColor,
  isValidSubjectName,
  normalizeSubjectName,
} from "@/lib/study-timer/utils";
import type { Database } from "@/types/database";
import type {
  CreateStudySubjectInput,
  RecordStudySessionInput,
  StudySubject,
  StudyTimerRepositoryResult,
  StudyTimerSession,
} from "@/types/study-timer";

type DbClient = SupabaseClient;

interface DbStudySubjectRow {
  id: string;
  user_id: string;
  name: string;
  color: string;
  total_seconds: number;
  created_at: string;
  updated_at: string;
}

interface DbStudyTimerSessionRow {
  id: string;
  user_id: string;
  subject_id: string;
  mode: "stopwatch" | "countdown";
  duration_seconds: number;
  started_at: string;
  ended_at: string;
  created_at: string;
}

function mapSubjectRow(row: DbStudySubjectRow): StudySubject {
  return {
    id: row.id,
    name: row.name,
    color: row.color,
    totalSeconds: Number(row.total_seconds),
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

function mapSessionRow(row: DbStudyTimerSessionRow): StudyTimerSession {
  return {
    id: row.id,
    subjectId: row.subject_id,
    mode: row.mode,
    durationSeconds: row.duration_seconds,
    startedAt: row.started_at,
    endedAt: row.ended_at,
    createdAt: row.created_at,
  };
}

export async function listCloudSubjects(
  client: DbClient,
  userId: string
): Promise<StudyTimerRepositoryResult<StudySubject[]>> {
  const { data, error } = await client
    .from("study_subjects")
    .select("*")
    .eq("user_id", userId)
    .order("updated_at", { ascending: false });

  if (error) {
    return { data: null, error: error.message };
  }

  return {
    data: (data as DbStudySubjectRow[]).map(mapSubjectRow),
    error: null,
  };
}

export async function createCloudSubject(
  client: DbClient,
  userId: string,
  input: CreateStudySubjectInput,
  colorIndex: number
): Promise<StudyTimerRepositoryResult<StudySubject>> {
  const name = normalizeSubjectName(input.name);

  if (!isValidSubjectName(name, SUBJECT_NAME_MAX_LENGTH)) {
    return { data: null, error: "科目名称不能为空且不超过 32 个字符" };
  }

  const insertPayload: Database["public"]["Tables"]["study_subjects"]["Insert"] =
    {
      user_id: userId,
      name,
      color: assignSubjectColor(colorIndex),
      total_seconds: 0,
    };

  const { data, error } = await client
    .from("study_subjects")
    .insert(insertPayload)
    .select("*")
    .single();

  if (error) {
    return { data: null, error: error.message };
  }

  return { data: mapSubjectRow(data as DbStudySubjectRow), error: null };
}

export async function getCloudSubjectById(
  client: DbClient,
  userId: string,
  subjectId: string
): Promise<StudyTimerRepositoryResult<StudySubject>> {
  const { data, error } = await client
    .from("study_subjects")
    .select("*")
    .eq("user_id", userId)
    .eq("id", subjectId)
    .maybeSingle();

  if (error) {
    return { data: null, error: error.message };
  }

  if (!data) {
    return { data: null, error: "科目不存在" };
  }

  return { data: mapSubjectRow(data as DbStudySubjectRow), error: null };
}

export async function recordCloudSession(
  client: DbClient,
  userId: string,
  input: RecordStudySessionInput
): Promise<StudyTimerRepositoryResult<StudyTimerSession>> {
  const startedAt = input.startedAt;
  const endedAt = input.endedAt;

  const { error: incrementError } = await client.rpc(
    "increment_subject_total_seconds",
    {
      p_subject_id: input.subjectId,
      p_user_id: userId,
      p_delta_seconds: input.durationSeconds,
    } as Record<string, string | number>
  );

  if (incrementError) {
    return { data: null, error: incrementError.message };
  }

  const { data, error } = await client
    .from("study_timer_sessions")
    .insert({
      user_id: userId,
      subject_id: input.subjectId,
      mode: input.mode,
      duration_seconds: input.durationSeconds,
      started_at: startedAt,
      ended_at: endedAt,
    })
    .select("*")
    .single();

  if (error) {
    return { data: null, error: error.message };
  }

  return { data: mapSessionRow(data as DbStudyTimerSessionRow), error: null };
}

export async function listCloudSessions(
  client: DbClient,
  userId: string
): Promise<StudyTimerRepositoryResult<StudyTimerSession[]>> {
  const { data, error } = await client
    .from("study_timer_sessions")
    .select("*")
    .eq("user_id", userId)
    .order("started_at", { ascending: false });

  if (error) {
    return { data: null, error: error.message };
  }

  return {
    data: (data as DbStudyTimerSessionRow[]).map(mapSessionRow),
    error: null,
  };
}

/** 同步：按科目名 upsert 并写入 sessions */
export async function upsertCloudSubjectByName(
  client: DbClient,
  userId: string,
  subject: StudySubject
): Promise<StudyTimerRepositoryResult<StudySubject>> {
  const { data: existing, error: queryError } = await client
    .from("study_subjects")
    .select("*")
    .eq("user_id", userId)
    .ilike("name", subject.name)
    .maybeSingle();

  if (queryError) {
    return { data: null, error: queryError.message };
  }

  if (existing) {
    const mergedTotal =
      Number((existing as DbStudySubjectRow).total_seconds) + subject.totalSeconds;

    const { data, error } = await client
      .from("study_subjects")
      .update({
        total_seconds: mergedTotal,
        color: subject.color,
      })
      .eq("id", (existing as DbStudySubjectRow).id)
      .select("*")
      .single();

    if (error) {
      return { data: null, error: error.message };
    }

    return { data: mapSubjectRow(data as DbStudySubjectRow), error: null };
  }

  const { data, error } = await client
    .from("study_subjects")
    .insert({
      user_id: userId,
      name: subject.name,
      color: subject.color,
      total_seconds: subject.totalSeconds,
    })
    .select("*")
    .single();

  if (error) {
    return { data: null, error: error.message };
  }

  return { data: mapSubjectRow(data as DbStudySubjectRow), error: null };
}

export async function insertCloudSessionIfNotExists(
  client: DbClient,
  userId: string,
  subjectId: string,
  session: StudyTimerSession
): Promise<StudyTimerRepositoryResult<StudyTimerSession>> {
  const { data: existing } = await client
    .from("study_timer_sessions")
    .select("id")
    .eq("user_id", userId)
    .eq("subject_id", subjectId)
    .eq("started_at", session.startedAt)
    .eq("duration_seconds", session.durationSeconds)
    .maybeSingle();

  if (existing) {
    return { data: session, error: null };
  }

  const { data, error } = await client
    .from("study_timer_sessions")
    .insert({
      user_id: userId,
      subject_id: subjectId,
      mode: session.mode,
      duration_seconds: session.durationSeconds,
      started_at: session.startedAt,
      ended_at: session.endedAt,
    })
    .select("*")
    .single();

  if (error) {
    return { data: null, error: error.message };
  }

  return { data: mapSessionRow(data as DbStudyTimerSessionRow), error: null };
}
