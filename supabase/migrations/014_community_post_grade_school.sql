-- 社区帖子：年级（必填）、院校（可选）

alter table public.community_posts
  add column if not exists grade text,
  add column if not exists university_id uuid references public.universities (id) on delete set null,
  add column if not exists university_name text;

comment on column public.community_posts.grade is '年级：23级–26级';
comment on column public.community_posts.university_id is '关联院校（可选）';
comment on column public.community_posts.university_name is '院校名称快照（展示用）';

create index if not exists idx_community_posts_grade on public.community_posts (grade);
create index if not exists idx_community_posts_university_id on public.community_posts (university_id);
