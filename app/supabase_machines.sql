-- Run once in Supabase SQL Editor if machines table is missing or RLS blocks writes.

create table if not exists public.machines (
  id text primary key,
  name text,
  manufacturer text,
  model text,
  serial_number text,
  location text,
  notes text,
  category text default 'ct_linac'
);

-- Add category if table existed without it
do $$ begin
  alter table public.machines add column if not exists category text default 'ct_linac';
exception when others then null;
end $$;

create table if not exists public.beams (
  id text primary key,
  machine_id text references public.machines(id) on delete cascade,
  modality text,
  nominal_energy text,
  measurement_depth_cm float,
  pdd float,
  k_q float,
  quality_index float,
  ssd_cm float,
  field_size text,
  nominal_output_cgy_mu float,
  notes text
);

alter table public.machines enable row level security;
alter table public.beams enable row level security;

-- Allow service_role full access (Render should use service_role key)
drop policy if exists machines_all on public.machines;
create policy machines_all on public.machines for all using (true) with check (true);

drop policy if exists beams_all on public.beams;
create policy beams_all on public.beams for all using (true) with check (true);

grant all on public.machines to anon, authenticated, service_role;
grant all on public.beams to anon, authenticated, service_role;
