-- 科目计时统计模块
-- study_subjects: 用户科目及累计时长
-- study_timer_sessions: 单次计时记录

-- ---------------------------------------------------------------------------
-- 1. study_subjects 学习科目
-- ---------------------------------------------------------------------------
create table public.study_subjects (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  name text not null,
  color text not null,
  total_seconds bigint not null default 0 check (total_seconds >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, name)
);

comment on table public.study_subjects is '用户学习科目及累计时长';
comment on column public.study_subjects.color is '科目标识色，十六进制色值';
comment on column public.study_subjects.total_seconds is '累计学习时长（秒）';

create index idx_study_subjects_user_id on public.study_subjects (user_id);

-- ---------------------------------------------------------------------------
-- 2. study_timer_sessions 计时记录
-- ---------------------------------------------------------------------------
create table public.study_timer_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  subject_id uuid not null references public.study_subjects (id) on delete cascade,
  mode text not null check (mode in ('stopwatch', 'countdown')),
  duration_seconds int not null check (duration_seconds > 0),
  started_at timestamptz not null,
  ended_at timestamptz not null,
  created_at timestamptz not null default now()
);

comment on table public.study_timer_sessions is '单次计时会话记录';
comment on column public.study_timer_sessions.mode is 'stopwatch=正向计时 countdown=倒计时';
comment on column public.study_timer_sessions.duration_seconds is '本次有效学习时长（秒）';

create index idx_study_timer_sessions_user_id on public.study_timer_sessions (user_id);
create index idx_study_timer_sessions_subject_id on public.study_timer_sessions (subject_id);
create index idx_study_timer_sessions_started_at on public.study_timer_sessions (started_at desc);

-- ---------------------------------------------------------------------------
-- updated_at
-- ---------------------------------------------------------------------------
create trigger set_study_subjects_updated_at
  before update on public.study_subjects
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
alter table public.study_subjects enable row level security;
alter table public.study_timer_sessions enable row level security;

create policy "users can manage own study subjects"
  on public.study_subjects for all using (auth.uid() = user_id);

create policy "users can manage own study timer sessions"
  on public.study_timer_sessions for all using (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- 原子累加科目时长（避免并发读写竞态）
-- ---------------------------------------------------------------------------
create or replace function public.increment_subject_total_seconds(
  p_subject_id uuid,
  p_user_id uuid,
  p_delta_seconds bigint
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.study_subjects
  set total_seconds = total_seconds + p_delta_seconds,
      updated_at = now()
  where id = p_subject_id
    and user_id = p_user_id;
end;
$$;
