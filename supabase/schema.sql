-- Run this in Supabase SQL Editor. The backend uses the service role key only.
create table if not exists public.calls (
  id uuid primary key,
  prospect text not null default 'New prospect',
  company text not null default '',
  current_stage text not null default 'open',
  stage_results jsonb not null default '[]'::jsonb,
  outcome text,
  notes text not null default '',
  started_at timestamptz not null default now(),
  ended_at timestamptz
);

alter table public.calls enable row level security;
-- No client policies: access is exclusively through the server-side service key.
create index if not exists calls_started_at_idx on public.calls (started_at desc);
