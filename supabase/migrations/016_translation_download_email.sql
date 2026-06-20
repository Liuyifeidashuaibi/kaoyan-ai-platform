-- Translator export delivery email (user-configured, separate from auth email)
alter table public.users
  add column if not exists translation_download_email text;

comment on column public.users.translation_download_email is
  'Email address for translator export attachments (Word/PDF/txt)';
