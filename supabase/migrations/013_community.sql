-- 社区模块：帖子、评论、关注、收藏
-- 复用 public.users，扩展 display_id / subject_category

-- ---------------------------------------------------------------------------
-- 1. users 扩展字段
-- ---------------------------------------------------------------------------
alter table public.users
  add column if not exists display_id text,
  add column if not exists subject_category text;

comment on column public.users.display_id is '社区用户 ID，用于搜索与 /user/{id} 路由';
comment on column public.users.subject_category is '专业大类（学科门类），取值与 SUBJECT_CATEGORIES 一致';

-- 为已有用户生成 display_id（nickname 或邮箱前缀，冲突时追加短 id）
update public.users u
set display_id = coalesce(
  nullif(
    lower(regexp_replace(coalesce(u.nickname, split_part(u.email, '@', 1)), '[^a-zA-Z0-9_]', '', 'g')),
    ''
  ),
  'user_' || left(replace(u.id::text, '-', ''), 8)
)
where u.display_id is null;

create unique index if not exists idx_users_display_id on public.users (display_id)
  where display_id is not null;

-- 新用户注册时写入 display_id
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
declare
  base_id text;
  final_id text;
  suffix int := 0;
begin
  base_id := coalesce(
    nullif(
      lower(regexp_replace(
        coalesce(new.raw_user_meta_data ->> 'nickname', split_part(new.email, '@', 1)),
        '[^a-zA-Z0-9_]', '', 'g'
      )),
      ''
    ),
    'user_' || left(replace(new.id::text, '-', ''), 8)
  );
  final_id := base_id;
  while exists (select 1 from public.users where display_id = final_id) loop
    suffix := suffix + 1;
    final_id := base_id || suffix::text;
  end loop;

  insert into public.users (id, email, nickname, avatar_url, display_id)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'nickname', split_part(new.email, '@', 1)),
    new.raw_user_meta_data ->> 'avatar_url',
    final_id
  );
  return new;
end;
$$;

-- 公开可读社区所需用户字段（保留 update 仅本人）
drop policy if exists "users can view own profile" on public.users;

create policy "public user profiles are viewable"
  on public.users for select using (true);

-- update 策略已在 001_core_schema 中创建，此处不重复

-- ---------------------------------------------------------------------------
-- 2. community_posts 帖子
-- ---------------------------------------------------------------------------
create table public.community_posts (
  id uuid primary key default gen_random_uuid(),
  author_id uuid not null references public.users (id) on delete cascade,
  post_type text not null check (post_type in ('experience', 'material')),
  subject_category text not null,
  title text not null,
  content text not null default '',
  attachments jsonb not null default '[]'::jsonb,
  view_count int not null default 0 check (view_count >= 0),
  favorite_count int not null default 0 check (favorite_count >= 0),
  comment_count int not null default 0 check (comment_count >= 0),
  hot_score int generated always as (favorite_count + comment_count + view_count) stored,
  is_hidden boolean not null default false,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.community_posts is '社区帖子（经验帖 / 资料帖）';
comment on column public.community_posts.attachments is '附件 JSON 数组：[{url, name, mime_type}]';

create index idx_community_posts_created_at on public.community_posts (created_at desc);
create index idx_community_posts_hot on public.community_posts (hot_score desc);
create index idx_community_posts_author on public.community_posts (author_id);
create index idx_community_posts_subject on public.community_posts (subject_category);
create index idx_community_posts_type on public.community_posts (post_type);

create trigger set_community_posts_updated_at
  before update on public.community_posts
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- 3. community_comments 评论 / 回复
-- ---------------------------------------------------------------------------
create table public.community_comments (
  id uuid primary key default gen_random_uuid(),
  post_id uuid not null references public.community_posts (id) on delete cascade,
  author_id uuid not null references public.users (id) on delete cascade,
  parent_id uuid references public.community_comments (id) on delete cascade,
  content text not null,
  created_at timestamptz not null default now()
);

comment on table public.community_comments is '帖子评论与回复';

create index idx_community_comments_post on public.community_comments (post_id, created_at asc);
create index idx_community_comments_parent on public.community_comments (parent_id);

-- ---------------------------------------------------------------------------
-- 4. user_follows 关注
-- ---------------------------------------------------------------------------
create table public.user_follows (
  follower_id uuid not null references public.users (id) on delete cascade,
  following_id uuid not null references public.users (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (follower_id, following_id),
  check (follower_id <> following_id)
);

comment on table public.user_follows is '用户关注关系';

create index idx_user_follows_following on public.user_follows (following_id);

-- ---------------------------------------------------------------------------
-- 5. post_favorites 收藏
-- ---------------------------------------------------------------------------
create table public.post_favorites (
  user_id uuid not null references public.users (id) on delete cascade,
  post_id uuid not null references public.community_posts (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, post_id)
);

comment on table public.post_favorites is '帖子收藏（用于最热排序与收藏页）';

create index idx_post_favorites_user on public.post_favorites (user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- 6. 计数维护触发器
-- ---------------------------------------------------------------------------
create or replace function public.sync_post_comment_count()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  if tg_op = 'INSERT' then
    update public.community_posts
    set comment_count = comment_count + 1
    where id = new.post_id;
  elsif tg_op = 'DELETE' then
    update public.community_posts
    set comment_count = greatest(comment_count - 1, 0)
    where id = old.post_id;
  end if;
  return coalesce(new, old);
end;
$$;

create trigger trg_comment_count
  after insert or delete on public.community_comments
  for each row execute function public.sync_post_comment_count();

create or replace function public.sync_post_favorite_count()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  if tg_op = 'INSERT' then
    update public.community_posts
    set favorite_count = favorite_count + 1
    where id = new.post_id;
  elsif tg_op = 'DELETE' then
    update public.community_posts
    set favorite_count = greatest(favorite_count - 1, 0)
    where id = old.post_id;
  end if;
  return coalesce(new, old);
end;
$$;

create trigger trg_favorite_count
  after insert or delete on public.post_favorites
  for each row execute function public.sync_post_favorite_count();

-- ---------------------------------------------------------------------------
-- 7. Row Level Security
-- ---------------------------------------------------------------------------
alter table public.community_posts enable row level security;
alter table public.community_comments enable row level security;
alter table public.user_follows enable row level security;
alter table public.post_favorites enable row level security;

-- 帖子：公开读未删除且未隐藏；作者可写
create policy "posts public read"
  on public.community_posts for select
  using (deleted_at is null and is_hidden = false);

create policy "authors read own hidden posts"
  on public.community_posts for select
  using (auth.uid() = author_id);

create policy "authenticated users create posts"
  on public.community_posts for insert
  with check (auth.uid() = author_id);

create policy "authors update own posts"
  on public.community_posts for update
  using (auth.uid() = author_id);

-- 评论：公开读；登录用户可发
create policy "comments public read"
  on public.community_comments for select using (true);

create policy "authenticated users create comments"
  on public.community_comments for insert
  with check (auth.uid() = author_id);

create policy "authors delete own comments"
  on public.community_comments for delete
  using (auth.uid() = author_id);

-- 关注
create policy "follows public read"
  on public.user_follows for select using (true);

create policy "users manage own follows"
  on public.user_follows for all
  using (auth.uid() = follower_id)
  with check (auth.uid() = follower_id);

-- 收藏
create policy "users read own favorites"
  on public.post_favorites for select
  using (auth.uid() = user_id);

create policy "users manage own favorites"
  on public.post_favorites for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- 8. Storage bucket（附件）
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('community-attachments', 'community-attachments', true)
on conflict (id) do nothing;

create policy "community attachments public read"
  on storage.objects for select
  using (bucket_id = 'community-attachments');

create policy "authenticated upload community attachments"
  on storage.objects for insert
  with check (
    bucket_id = 'community-attachments'
    and auth.role() = 'authenticated'
  );

create policy "users delete own community attachments"
  on storage.objects for delete
  using (
    bucket_id = 'community-attachments'
    and auth.uid()::text = (storage.foldername(name))[1]
  );
