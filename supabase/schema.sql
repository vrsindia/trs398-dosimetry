-- DOSE pro – Supabase schema (run in Supabase SQL Editor)
-- Free tier compatible

-- Department (single row)
create table if not exists department (
  id text primary key default 'dept',
  name text default 'Department of Radiation Oncology',
  hospital text default '',
  address text default '',
  city text default '',
  country text default '',
  phone text default '',
  email text default '',
  head_physicist text default '',
  logo_url text default '',
  notes text default '',
  updated_at timestamptz default now()
);

insert into department (id) values ('dept') on conflict (id) do nothing;

-- Users
create table if not exists app_users (
  id text primary key,
  username text unique not null,
  full_name text not null,
  role text not null check (role in ('developer','admin','physicist','intern','observer')),
  password_hash text not null,
  salt text not null,
  active boolean default true,
  permissions text[] default '{}',
  created_at timestamptz default now(),
  created_by text default ''
);

-- Detectors
create table if not exists detectors (
  id text primary key,
  name text not null,
  detector_type text not null,
  serial_number text default '',
  calibration_factor double precision not null,
  calibration_quality text default 'Co-60',
  calibration_date text,
  calibration_lab text,
  next_due_date text,
  notes text default '',
  unit text default 'Gy/nC'
);

-- Machines (linacs)
create table if not exists machines (
  id text primary key,
  name text not null,
  manufacturer text default '',
  model text default '',
  serial_number text default '',
  location text default '',
  notes text default ''
);

-- Beams
create table if not exists beams (
  id text primary key,
  machine_id text not null references machines(id) on delete cascade,
  modality text not null,
  nominal_energy text not null,
  measurement_depth_cm double precision not null,
  pdd double precision default 1.0,
  k_q double precision default 1.0,
  quality_index double precision,
  ssd_cm double precision default 100.0,
  field_size text default '10x10',
  nominal_output_cgy_mu double precision default 1.0,
  notes text default ''
);

create index if not exists beams_machine_idx on beams(machine_id);

-- Tolerances
create table if not exists tolerances (
  id text primary key,
  name text not null,
  machine_id text,
  modality text default 'photon',
  energy text,
  parameter text default 'output',
  tolerance_percent double precision default 2.0,
  action_level_percent double precision,
  baseline_value double precision,
  notes text default ''
);

-- Calc profiles
create table if not exists calc_profiles (
  id text primary key,
  name text not null,
  use_k_tp boolean default true,
  use_k_pol boolean default true,
  use_k_s boolean default true,
  use_k_q boolean default true,
  use_electrometer_factor boolean default true,
  use_k_other boolean default false,
  use_pdd_correction boolean default false,
  notes text default '',
  is_default boolean default false
);

-- Output history
create table if not exists output_records (
  id text primary key,
  machine_id text not null,
  beam_id text,
  modality text not null,
  energy text not null,
  date_time timestamptz not null default now(),
  measured_output_cgy_mu double precision not null,
  tuned_output_cgy_mu double precision,
  tuning_performed boolean default false,
  detector_id text,
  k_tp double precision default 1.0,
  k_pol double precision default 1.0,
  k_s double precision default 1.0,
  k_q double precision default 1.0,
  notes text default '',
  physicist text default '',
  nominal_output_cgy_mu double precision default 1.0,
  status text default 'unknown',
  raw_readings double precision[] default '{}',
  average_reading_nc double precision,
  tpr20_10 double precision,
  saved_for_report boolean default false
);

create index if not exists output_machine_date_idx on output_records(machine_id, date_time);

-- Reports
create table if not exists reports (
  id text primary key,
  machine_id text not null,
  machine_name text not null,
  report_date date not null,
  created_at timestamptz default now(),
  created_by text default '',
  title text not null,
  modality text default 'mixed',
  measurement_ids text[] default '{}',
  notes text default '',
  summary jsonb default '{}'
);

-- Pending approvals
create table if not exists pending_changes (
  id text primary key,
  entity_type text not null,
  entity_id text not null,
  action text not null,
  proposed_data jsonb not null,
  original_data jsonb,
  requested_by text default '',
  requested_at timestamptz default now(),
  status text default 'pending',
  reviewed_by text default '',
  reviewed_at timestamptz,
  comment text default ''
);

-- Enable open access for service role / anon key from backend only
-- (app uses service role or anon from server; do not expose service key in browser)

alter table department enable row level security;
alter table app_users enable row level security;
alter table detectors enable row level security;
alter table machines enable row level security;
alter table beams enable row level security;
alter table tolerances enable row level security;
alter table calc_profiles enable row level security;
alter table output_records enable row level security;
alter table reports enable row level security;
alter table pending_changes enable row level security;

-- Policies: allow all for anon/authenticated when using server-side key
-- For free-tier backend-only app we use service role key (bypasses RLS).
-- If using anon key, create permissive policies:

do $$
begin
  -- department
  if not exists (select 1 from pg_policies where tablename = 'department' and policyname = 'allow_all_dept') then
    create policy allow_all_dept on department for all using (true) with check (true);
  end if;
  if not exists (select 1 from pg_policies where tablename = 'app_users' and policyname = 'allow_all_users') then
    create policy allow_all_users on app_users for all using (true) with check (true);
  end if;
  if not exists (select 1 from pg_policies where tablename = 'detectors' and policyname = 'allow_all_det') then
    create policy allow_all_det on detectors for all using (true) with check (true);
  end if;
  if not exists (select 1 from pg_policies where tablename = 'machines' and policyname = 'allow_all_mach') then
    create policy allow_all_mach on machines for all using (true) with check (true);
  end if;
  if not exists (select 1 from pg_policies where tablename = 'beams' and policyname = 'allow_all_beams') then
    create policy allow_all_beams on beams for all using (true) with check (true);
  end if;
  if not exists (select 1 from pg_policies where tablename = 'tolerances' and policyname = 'allow_all_tol') then
    create policy allow_all_tol on tolerances for all using (true) with check (true);
  end if;
  if not exists (select 1 from pg_policies where tablename = 'calc_profiles' and policyname = 'allow_all_prof') then
    create policy allow_all_prof on calc_profiles for all using (true) with check (true);
  end if;
  if not exists (select 1 from pg_policies where tablename = 'output_records' and policyname = 'allow_all_out') then
    create policy allow_all_out on output_records for all using (true) with check (true);
  end if;
  if not exists (select 1 from pg_policies where tablename = 'reports' and policyname = 'allow_all_rep') then
    create policy allow_all_rep on reports for all using (true) with check (true);
  end if;
  if not exists (select 1 from pg_policies where tablename = 'pending_changes' and policyname = 'allow_all_pend') then
    create policy allow_all_pend on pending_changes for all using (true) with check (true);
  end if;
end $$;
