-- 考研 AI 平台核心表结构
-- 7 张核心表：auth.users（Supabase 内置）+ 6 张 public 业务表（均通过 users 关联 auth.users）

-- ---------------------------------------------------------------------------
-- 1. schools 院校
-- ---------------------------------------------------------------------------
create table public.schools (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  code text unique,
  province text,
  city text,
  level text,
  website text,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.schools is '院校信息';

-- ---------------------------------------------------------------------------
-- 2. majors 专业
-- ---------------------------------------------------------------------------
create table public.majors (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  name text not null,
  code text,
  category text,
  degree_type text,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (school_id, code)
);

comment on table public.majors is '院校专业';

create index idx_majors_school_id on public.majors (school_id);

-- ---------------------------------------------------------------------------
-- 3. users 用户扩展（关联 auth.users）
-- ---------------------------------------------------------------------------
create table public.users (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  nickname text,
  avatar_url text,
  bio text,
  target_year int,
  target_school_id uuid references public.schools (id) on delete set null,
  target_major_id uuid references public.majors (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.users is '用户资料，主键关联 auth.users';

-- 新用户注册时自动创建 public.users 记录
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.users (id, email, nickname, avatar_url)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'nickname', split_part(new.email, '@', 1)),
    new.raw_user_meta_data ->> 'avatar_url'
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- 4. study_records 学习记录（含番茄钟）
-- ---------------------------------------------------------------------------
create table public.study_records (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  subject text not null,
  duration_minutes int not null default 0 check (duration_minutes >= 0),
  pomodoro_count int not null default 0 check (pomodoro_count >= 0),
  notes text,
  studied_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

comment on table public.study_records is '学习/番茄钟记录';

create index idx_study_records_user_id on public.study_records (user_id);
create index idx_study_records_studied_at on public.study_records (studied_at desc);

-- ---------------------------------------------------------------------------
-- 5. chat_messages AI 聊天消息
-- ---------------------------------------------------------------------------
create table public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  session_id text not null default gen_random_uuid()::text,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,
  created_at timestamptz not null default now()
);

comment on table public.chat_messages is 'AI 聊天消息';

create index idx_chat_messages_user_id on public.chat_messages (user_id);
create index idx_chat_messages_session_id on public.chat_messages (session_id);

-- ---------------------------------------------------------------------------
-- 6. admission_data 录取数据
-- ---------------------------------------------------------------------------
create table public.admission_data (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  major_id uuid not null references public.majors (id) on delete cascade,
  year int not null,
  enrollment_count int,
  applicant_count int,
  min_score numeric(6, 2),
  max_score numeric(6, 2),
  avg_score numeric(6, 2),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (school_id, major_id, year)
);

comment on table public.admission_data is '历年录取数据';

create index idx_admission_data_school_id on public.admission_data (school_id);
create index idx_admission_data_major_id on public.admission_data (major_id);
create index idx_admission_data_year on public.admission_data (year desc);

-- ---------------------------------------------------------------------------
-- updated_at 自动更新
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger set_schools_updated_at
  before update on public.schools
  for each row execute function public.set_updated_at();

create trigger set_majors_updated_at
  before update on public.majors
  for each row execute function public.set_updated_at();

create trigger set_users_updated_at
  before update on public.users
  for each row execute function public.set_updated_at();

create trigger set_admission_data_updated_at
  before update on public.admission_data
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
alter table public.schools enable row level security;
alter table public.majors enable row level security;
alter table public.users enable row level security;
alter table public.study_records enable row level security;
alter table public.chat_messages enable row level security;
alter table public.admission_data enable row level security;

-- 公开只读：院校、专业、录取数据
create policy "schools are viewable by everyone"
  on public.schools for select using (true);

create policy "majors are viewable by everyone"
  on public.majors for select using (true);

create policy "admission_data is viewable by everyone"
  on public.admission_data for select using (true);

-- 用户资料
create policy "users can view own profile"
  on public.users for select using (auth.uid() = id);

create policy "users can update own profile"
  on public.users for update using (auth.uid() = id);

-- 学习记录
create policy "users can manage own study records"
  on public.study_records for all using (auth.uid() = user_id);

-- 聊天消息
create policy "users can manage own chat messages"
  on public.chat_messages for all using (auth.uid() = user_id);
