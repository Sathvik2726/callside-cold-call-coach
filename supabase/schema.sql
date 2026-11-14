-- Run this in Supabase SQL Editor. The backend uses the service role key only.
create table if not exists public.calls (
  id uuid primary key,
  prospect text not null default 'New prospect',
  company text not null default '',
  current_stage text not null default 'opening',
  outcome text,
  next_step text not null default '',
  next_step_details text not null default '',
  notes text not null default '',
  started_at timestamptz not null default now(),
  ended_at timestamptz
);

alter table public.calls enable row level security;
-- No client policies: access is exclusively through the server-side service key.
create index if not exists calls_started_at_idx on public.calls (started_at desc);

create table if not exists public.call_stage_results (
  id bigint generated always as identity primary key,
  call_id uuid not null references public.calls(id) on delete cascade,
  stage_id text not null,
  stage_name text not null,
  outcome text not null,
  prospect_words text not null default '',
  saved_at timestamptz not null default now(),
  unique (call_id, stage_id)
);

alter table public.call_stage_results enable row level security;
create index if not exists call_stage_results_call_id_idx on public.call_stage_results (call_id, saved_at);
