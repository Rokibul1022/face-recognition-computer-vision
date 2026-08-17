-- AI CCTV Monitoring Agent — Supabase (PostgreSQL + pgvector) schema.
--
-- This is the drop-in production schema. The local SQLite store in
-- app/db/store.py mirrors it table-for-table; swap the Store backend and the
-- agent pipeline is unchanged.
--
-- Setup:
--   1. In Supabase SQL editor, run this whole file.
--   2. Enable the vector extension (first line).
--   3. Point FR_DB_STORE=supabase + SUPABASE_URL / SUPABASE_SERVICE_KEY at it.

create extension if not exists vector;

-- Cameras
create table cameras (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  location      text,
  zone          text,
  active        boolean default true,
  created_at    timestamptz default now()
);

-- Known faces / identities
create table faces (
  id            uuid primary key default gen_random_uuid(),
  full_name     text,
  role          text,              -- e.g. employee, contractor
  embedding     vector(512),       -- InsightFace embedding size
  reference_img_url text,
  created_at    timestamptz default now()
);

-- Users (dashboard / notification recipients)
create table users (
  id            uuid primary key default gen_random_uuid(),
  email         text unique not null,
  phone         text,
  telegram_id   text,
  role          text default 'viewer',   -- admin | security | viewer
  created_at    timestamptz default now()
);

-- Raw events from the CV pipeline
create table events (
  id                    uuid primary key default gen_random_uuid(),
  camera_id             uuid references cameras(id),
  track_id              integer,
  identity_face_id       uuid references faces(id),
  identity_label        text,             -- "unknown" or resolved name
  identity_confidence    numeric,
  detection_type        text,             -- person | vehicle | weapon | fire | ...
  bbox                  jsonb,
  duration_in_frame_sec  numeric,
  snapshot_url          text,
  raw_payload           jsonb,
  created_at            timestamptz default now()
);

-- Semantic embeddings for long-term memory / RAG
create table event_embeddings (
  id            uuid primary key default gen_random_uuid(),
  event_id      uuid references events(id) on delete cascade,
  description   text,              -- natural-language summary of the event
  embedding     vector(1536),      -- text-embedding model dim
  created_at    timestamptz default now()
);

-- Agent decisions/incidents (post-reasoning)
create table incidents (
  id                    uuid primary key default gen_random_uuid(),
  event_id              uuid references events(id),
  severity              text check (severity in ('INFO','WARNING','CRITICAL')),
  action                text check (action in ('notify','log_only','ignore','escalate')),
  reasoning             text,
  reference_incident_id uuid references incidents(id),
  resolved              boolean default false,
  created_at            timestamptz default now()
);

-- Alerts sent out
create table alerts (
  id            uuid primary key default gen_random_uuid(),
  incident_id   uuid references incidents(id),
  channel       text,              -- telegram | email | slack | discord
  recipient     text,
  status        text default 'pending',  -- pending | sent | failed
  sent_at       timestamptz,
  created_at    timestamptz default now()
);

-- Conversation history (natural-language chat interface)
create table conversations (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid references users(id),
  role          text check (role in ('user','assistant')),
  content       text,
  created_at    timestamptz default now()
);

-- System/audit logs
create table logs (
  id            uuid primary key default gen_random_uuid(),
  level         text,
  source        text,
  message       text,
  created_at    timestamptz default now()
);

-- Indexes for vector search
create index on event_embeddings using ivfflat (embedding vector_cosine_ops) with (lists = 100);
create index on faces using ivfflat (embedding vector_cosine_ops) with (lists = 50);

-- Realtime push for the dashboard (incidents + alerts)
alter publication supabase_realtime add table incidents;
alter publication supabase_realtime add table alerts;
alter publication supabase_realtime add table events;