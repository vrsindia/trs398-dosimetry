-- DOSE pro / GARUDA — Supabase schema
-- Run in Supabase SQL editor once. Set SUPABASE_URL + SUPABASE_KEY on Render.

create table if not exists department (
  id text primary key default 'dept',
  name text, hospital text, address text, city text, country text,
  phone text, email text, head_physicist text, logo_url text, notes text,
  updated_at timestamptz default now()
);

create table if not exists app_users (
  id text primary key,
  username text unique not null,
  full_name text,
  role text not null,
  password_hash text not null,
  salt text not null,
  active boolean default true,
  permissions jsonb default '[]',
  created_at text,
  created_by text
);

create table if not exists tolerances (
  id text primary key,
  name text not null,
  linac_id text,
  modality text default 'photon',
  energy text,
  parameter text default 'output',
  tolerance_percent float default 2.0,
  action_level_percent float,
  baseline_value float,
  notes text
);

create table if not exists detectors (
  id text primary key,
  name text, detector_type text, serial_number text,
  calibration_factor float, calibration_quality text,
  calibration_date text, calibration_lab text, next_due_date text,
  notes text, unit text
);

create table if not exists machines (
  id text primary key,
  name text, manufacturer text, model text,
  serial_number text, location text, notes text,
  category text default 'ct_linac'
);

create table if not exists beams (
  id text primary key,
  machine_id text references machines(id) on delete cascade,
  modality text, nominal_energy text,
  measurement_depth_cm float, pdd float, k_q float,
  quality_index float, ssd_cm float, field_size text,
  nominal_output_cgy_mu float, notes text
);

create table if not exists output_records (
  id text primary key,
  machine_id text, beam_id text, modality text, energy text,
  date_time text, measured_output_cgy_mu float,
  tuned_output_cgy_mu float, tuning_performed boolean,
  detector_id text, k_tp float, k_pol float, k_s float, k_q float,
  notes text, physicist text, nominal_output_cgy_mu float,
  status text, raw_readings jsonb, average_reading_nc float,
  tpr20_10 float, saved_for_report boolean
);
