-- Run once in Supabase SQL editor so users persist across Render restarts.

create table if not exists public.app_users (
  id text primary key,
  username text not null unique,
  full_name text,
  role text not null default 'observer',
  password_hash text not null,
  salt text not null,
  active boolean not null default true,
  permissions jsonb not null default '[]'::jsonb,
  created_at text,
  created_by text
);

create index if not exists app_users_username_idx on public.app_users (username);

-- Allow service role full access (Render uses service_role or anon key)
alter table public.app_users enable row level security;

-- Simple policy: authenticated/service can do all (adjust for production)
drop policy if exists "app_users_all" on public.app_users;
create policy "app_users_all" on public.app_users
  for all
  using (true)
  with check (true);
