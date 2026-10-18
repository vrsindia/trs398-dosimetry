-- Run in Supabase SQL editor once
-- Stores Daily QA and Mechanical QA evaluation sessions

create table if not exists qa_results (
  id text primary key,
  kind text not null check (kind in ('daily', 'mechanical')),
  linac_id text,
  linac_name text,
  performed_at timestamptz not null default now(),
  performed_by text,
  overall text,
  results jsonb default '[]'::jsonb,
  notes text
);

create index if not exists qa_results_kind_idx on qa_results (kind);
create index if not exists qa_results_linac_idx on qa_results (linac_id);
create index if not exists qa_results_performed_idx on qa_results (performed_at desc);

-- Optional RLS: service role key bypasses RLS; enable if using anon key with policies
