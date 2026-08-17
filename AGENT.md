# AGENT.md — AI CCTV Monitoring Agent

> Vision + Agentic AI system that watches live CCTV streams, understands what it sees, reasons about it like a security officer, remembers it, and acts on it.

---

## 1. Project Overview

**Name:** AI CCTV Monitoring Agent
**Type:** Multi-agent surveillance system (Computer Vision + LLM Agent + Memory)
**Core Idea:** Don't just detect people — *understand* what's happening, *decide* if it matters, *remember* it, and *notify* the right people.

```
Camera → Detect → Recognize → Analyze → Reason → Act → Remember → Notify
```

The system is split into two decoupled pipelines that communicate through a shared event bus and a shared database:

1. **CV Pipeline** — real-time, GPU-bound, deterministic (detection, tracking, recognition).
2. **Agent Pipeline** — event-driven, LLM-bound, reasoning-based (classification, memory, decisions, chat).

Keeping these separate means the CV side can run at 15–30 FPS on local hardware while the LLM agent only wakes up when something worth reasoning about actually happens.

---

## 2. Design Principles

- **Event-driven, not frame-driven.** The LLM never sees raw video. It only sees structured `Event` objects the CV pipeline emits.
- **Confidence-gated actions.** No alert fires below a configured confidence threshold — false positives are the #1 way trust in a security system dies.
- **Two-tier memory.** Short-term (current incident / active session context) vs. long-term (historical, embedded, queryable).
- **Severity before noise.** Every event is classified `INFO / WARNING / CRITICAL` before any notification logic runs.
- **One database.** A single Postgres instance (Supabase) holds relational data *and* vector embeddings — no separate vector store to keep in sync.
- **Human-in-the-loop by default.** The agent notifies and explains; it does not auto-lock doors or call police without explicit escalation rules.

---

## 3. Updated Tech Stack

| Layer | Old | **New** |
|---|---|---|
| Database | SQLite | **Supabase (PostgreSQL)** |
| Vector store | ChromaDB / FAISS | **pgvector (inside Supabase)** |
| File storage | local `screenshots/` | **Supabase Storage** (buckets for snapshots/clips) |
| Backend hosting | local | **Render** |
| Frontend hosting | local | **Netlify** |
| Backend | FastAPI | FastAPI (unchanged) |
| Vision | YOLOv11, InsightFace, DeepSORT | unchanged |
| Agent framework | LangGraph, LangChain, MCP | unchanged |
| Frontend | React / Next.js | unchanged |

**Why Supabase Postgres + pgvector over SQLite + ChromaDB:**
- One connection string, one backup policy, one place to query relational + semantic data together (`SELECT ... ORDER BY embedding <-> query_embedding`).
- Row-Level Security for multi-camera / multi-tenant access control.
- Built-in Storage + Auth + Realtime (can push new events to the dashboard via Supabase Realtime instead of polling).
- Scales from a single Raspberry Pi demo to a multi-site deployment without a migration.

---

## 4. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                            EDGE / LOCAL                               │
│                                                                        │
│   Camera(s) ──▶ Frame Capture ──▶ YOLOv11 Detection ──▶ DeepSORT      │
│                                         │            Tracking          │
│                                         ▼                              │
│                              InsightFace Recognition                   │
│                                         │                              │
│                                         ▼                              │
│                               Event Generator                          │
└──────────────────────────────────┬───────────────────────────────────┘
                                    │  structured Event (JSON)
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         AGENT LAYER (Cloud/Server)                    │
│                                                                        │
│   Event Queue ──▶ Perception Agent ──▶ Severity Classifier            │
│                                            │                           │
│                                            ▼                           │
│                                     Reasoning Agent (LLM)              │
│                                     ├── reads Short-Term Memory        │
│                                     ├── reads Long-Term Memory (RAG)   │
│                                     └── writes Decision                │
│                                            │                           │
│                              ┌─────────────┼─────────────┐            │
│                              ▼             ▼             ▼            │
│                        Memory Agent   Notifier Agent  Report Agent    │
│                              │             │             │            │
└──────────────────────────────┼─────────────┼─────────────┼───────────┘
                                ▼             ▼             ▼
                        Supabase (Postgres  Telegram/      Dashboard /
                        + pgvector + Storage) Email/Slack   Weekly PDF
                                    ▲
                                    │
                        FastAPI Backend (REST + WebSocket)
                                    ▲
                                    │
                     React / Next.js Dashboard (Netlify) + Chat UI
```

**Deployment split:**
- **Edge/local process:** CV pipeline (needs GPU/webcam access) — runs on-prem or on a local server/NUC.
- **Cloud process (Render):** FastAPI + LangGraph agents — receives events over HTTPS/WebSocket from the edge.
- **Frontend (Netlify):** Next.js dashboard + chat interface, talks to Render backend.
- **Supabase:** database, vector store, file storage, auth, realtime — the shared source of truth.

---

## 5. Multi-Agent Workflow (LangGraph)

The reasoning side is modeled as a LangGraph state graph with five specialized agents, not one monolithic prompt.

```
                     ┌────────────────────┐
                     │   Perception Agent  │  ← normalizes raw CV event
                     └─────────┬───────────┘
                               ▼
                     ┌────────────────────┐
                     │ Severity Classifier │  ← INFO / WARNING / CRITICAL
                     └─────────┬───────────┘
                               ▼
                     ┌────────────────────┐
                     │  Reasoning Agent    │  ← core decision-maker
                     │  (context + memory) │
                     └─────────┬───────────┘
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌────────────────┐ ┌─────────────┐ ┌────────────────┐
     │  Memory Agent   │ │ Notifier    │ │ Report Agent    │
     │  (write STM/LTM)│ │ Agent       │ │ (daily/weekly)  │
     └────────────────┘ └─────────────┘ └────────────────┘
```

### 5.1 Perception Agent
- Input: raw `Event` JSON from the CV pipeline.
- Normalizes fields, resolves camera metadata, attaches the snapshot URL from Supabase Storage.
- Deduplicates near-identical events (same `person_id` within N seconds on the same camera).

### 5.2 Severity Classifier
- Rule-based **first pass** (cheap, deterministic) using confidence + context (time of day, zone, known/unknown):
  - `INFO`: known employee, normal hours, single entry.
  - `WARNING`: unknown person during business hours, loitering 2–5 min, tailgating.
  - `CRITICAL`: unknown person after hours, weapon/fire/smoke flag, loitering >10 min, crowd surge.
- LLM **second pass** only for ambiguous cases (confidence 0.4–0.7, or conflicting signals) — keeps token spend low.

### 5.3 Reasoning Agent (the core LLM agent)
- Pulls **short-term memory** (last N events on this camera / this person in the current session).
- Pulls **long-term memory** via pgvector similarity search ("has this person or pattern appeared before?").
- Produces a structured `Decision`:
  ```json
  {
    "action": "notify | log_only | ignore | escalate",
    "severity": "INFO | WARNING | CRITICAL",
    "reasoning": "short explanation",
    "reference_incident_id": "uuid or null"
  }
  ```
- Explicitly references prior incidents when relevant, e.g. *"Same unknown person as 10 PM yesterday at Gate-1."*

### 5.4 Memory Agent
- Writes the event + embedding to long-term memory (Postgres + pgvector).
- Updates short-term memory (Redis or in-process TTL cache) for the active session/incident.
- Prunes short-term memory after a configurable idle period (e.g., 30 min of no new events on that camera).

### 5.5 Notifier Agent
- Applies **confidence thresholds** and **channel routing rules** before sending.
- Batches low-severity events into digest notifications; sends CRITICAL immediately.
- Supports Telegram, Email, Slack, Discord now; WhatsApp/SMS as future channels.

### 5.6 Report Agent (Phase 3)
- Runs on a schedule (daily/weekly cron via Render Cron Jobs).
- Queries Supabase for the period's events, summarizes via LLM, generates a PDF/HTML report, stores it in Supabase Storage, and emails/Slacks a link.

---

## 6. Computer Vision Pipeline

```
Camera Stream
     │
     ▼
Frame Capture (OpenCV, configurable FPS sampling)
     │
     ▼
Person/Object Detection (YOLOv11)
     │
     ▼
Multi-Object Tracking (DeepSORT) ── assigns persistent track_id
     │
     ▼
Face Detection + Recognition (InsightFace / FaceNet) ── matches against known-faces embeddings
     │
     ▼
Event Generator ── builds structured Event, uploads snapshot to Supabase Storage
     │
     ▼
POST /events  (to FastAPI backend, which enqueues for the Agent layer)
```

**Event schema (emitted by CV pipeline):**
```json
{
  "event_id": "uuid",
  "camera_id": "gate-1",
  "track_id": 23,
  "identity": "unknown | employee_name",
  "identity_confidence": 0.94,
  "detection_type": "person | vehicle | weapon | fire | smoke | crowd",
  "bbox": [x1, y1, x2, y2],
  "duration_in_frame_sec": 12.4,
  "timestamp": "2026-08-16T22:14:03Z",
  "snapshot_url": "supabase://storage/events/gate-1/xxxx.jpg"
}
```

**Phase-by-phase CV scope:**
- **Phase 1 (MVP):** person + face detection, recognition, timestamp logging, event DB, screenshots.
- **Future additions:** weapon detection, fire/smoke detection, PPE detection, vehicle + license plate recognition, crowd detection, fall detection, violence detection — each becomes an additional YOLO detection head or a dedicated fine-tuned model feeding the same `Event` schema via a `detection_type` field, so the agent layer needs no changes to support new detectors.

---

## 7. Memory Architecture

| Tier | Store | Lifetime | Purpose |
|---|---|---|---|
| **Short-term memory** | In-process cache / Redis | Minutes (active incident window) | "Is this the same loitering event I saw 3 minutes ago?" |
| **Long-term memory** | Postgres + pgvector | Permanent (or retention-policy bound) | "Has this face/pattern appeared before? What happened last time?" |
| **Conversation memory** | Postgres (`conversations` table) | Per session | Chat history for the natural-language interface |

**Long-term memory retrieval flow:**
1. New event arrives → generate embedding (face embedding + a text description embedding of the event).
2. Vector similarity search in `event_embeddings` (pgvector `<->` cosine/L2 operator) for the top-k similar past incidents.
3. Reasoning Agent receives those as context: *"3 similar past events found, 2 were flagged CRITICAL."*
4. Agent's decision + reasoning gets stored back, closing the loop for future recall.

---

## 8. Database Schema — Supabase PostgreSQL + pgvector

```sql
-- Enable extension
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
```

### 8.1 ER Diagram (simplified)

```
cameras ──┬──< events >──┬── faces
          │               │
          │               └──< event_embeddings
          │
incidents >── events
    │
    ├──< alerts
    │
    └── incidents (self-ref: reference_incident_id)

users ──< conversations
users ──< alerts (via recipient)
```

---

## 9. FastAPI Backend

### 9.1 Structure
```
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── db/
│   │   └── supabase_client.py
│   ├── vision/            # ingestion endpoints only; heavy CV runs at the edge
│   ├── agent/
│   │   ├── graph.py        # LangGraph state graph definition
│   │   ├── perception.py
│   │   ├── severity.py
│   │   ├── reasoning.py
│   │   ├── memory.py
│   │   ├── notifier.py
│   │   └── report.py
│   ├── memory/
│   │   ├── short_term.py
│   │   └── long_term.py    # pgvector queries
│   ├── events/
│   │   └── router.py
│   ├── api/
│   │   └── router.py
│   ├── notifications/
│   │   ├── telegram.py
│   │   ├── email.py
│   │   ├── slack.py
│   │   └── discord.py
│   └── websocket/
│       └── realtime.py
├── tests/
├── Dockerfile
└── requirements.txt
```

### 9.2 API Specification

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/events` | CV pipeline pushes a new detected event |
| `GET` | `/events` | List/filter events (camera, date range, identity) |
| `GET` | `/events/{id}` | Get single event with snapshot + linked incident |
| `GET` | `/faces` | List known faces |
| `POST` | `/faces` | Register a new known face (name + reference image) |
| `POST` | `/recognize` | On-demand face recognition against an uploaded image |
| `GET` | `/incidents` | List agent-classified incidents (filter by severity) |
| `POST` | `/incidents/{id}/resolve` | Mark an incident as resolved |
| `POST` | `/alert` | Manually trigger an alert |
| `GET` | `/summary` | Daily/weekly summary (delegates to Report Agent) |
| `GET` | `/camera/{id}` | Camera metadata + recent activity |
| `POST` | `/chat` | Natural-language query against event/incident memory |
| `WS` | `/ws/live` | Realtime push of new events/incidents to the dashboard |

### 9.3 Agent Prompts (representative)

**Severity Classifier (LLM fallback for ambiguous cases):**
```
You are a security severity classifier. Given an event and camera context,
classify it as INFO, WARNING, or CRITICAL.

Event: {event_json}
Camera zone: {zone}
Time of day: {time}
Known identity: {identity_or_unknown}

Rules:
- Unknown person + after hours -> lean CRITICAL
- Known employee, normal hours -> INFO
- Loitering over 5 minutes -> at least WARNING
- Any weapon/fire/smoke flag -> CRITICAL regardless of other factors

Respond ONLY with JSON: {"severity": "...", "reason": "..."}
```

**Reasoning Agent:**
```
You are a security reasoning agent reviewing a new event.

New event: {event_json}
Severity (pre-classified): {severity}
Similar past incidents (top-5, from long-term memory): {similar_incidents}
Current short-term context (this camera, last 30 min): {short_term_memory}

Decide the action: notify, log_only, ignore, or escalate.
If this event resembles a past incident, reference it explicitly by id.
Explain your reasoning in 1-2 sentences, written for a human security officer.

Respond ONLY with JSON:
{"action": "...", "reasoning": "...", "reference_incident_id": "... or null"}
```

**Chat / Natural-Language Interface:**
```
You are a surveillance assistant answering questions using only the retrieved
events and incidents provided below. Never invent data not present in context.

Retrieved context: {rag_results}
User question: {user_message}

Answer concisely and cite camera + timestamp when relevant.
```

---

## 10. Sequence Diagrams

### 10.1 Event → Notification Flow
```
CV Pipeline        FastAPI          LangGraph Agents        Supabase        Notifier
    │  POST /events   │                     │                    │              │
    │ ───────────────▶│                     │                    │              │
    │                 │  enqueue event      │                    │              │
    │                 │ ───────────────────▶│                    │              │
    │                 │                     │ read short/long-term memory        │
    │                 │                     │ ──────────────────▶│              │
    │                 │                     │◀────────────────── │              │
    │                 │                     │ classify + reason  │              │
    │                 │                     │ write incident      │              │
    │                 │                     │ ──────────────────▶│              │
    │                 │                     │ if action=notify/escalate          │
    │                 │                     │ ───────────────────────────────────▶│
    │                 │                     │                    │  send alert   │
    │                 │  WS push to dashboard│                    │              │
    │                 │◀────────────────────│                    │              │
```

### 10.2 Chat Query Flow
```
User        Dashboard      FastAPI       Reasoning/RAG      Supabase (pgvector)
 │ "Who entered today?"       │              │                     │
 │ ──────────────────▶│──────▶│─────────────▶│                     │
 │                     │       │              │  embed query        │
 │                     │       │              │ ────────────────────▶│
 │                     │       │              │◀──── top-k matches ──│
 │                     │       │              │  compose answer      │
 │                     │       │◀─────────────│                     │
 │◀──── answer ────────│◀──────│                                    │
```

---

## 11. Frontend — React / Next.js Dashboard

```
frontend/
├── app/
│   ├── page.tsx              # live dashboard (camera grid + latest events)
│   ├── incidents/page.tsx    # incident list, filter by severity
│   ├── faces/page.tsx        # manage known faces
│   ├── chat/page.tsx         # natural-language Q&A interface
│   └── settings/page.tsx     # notification channels, thresholds
├── components/
│   ├── CameraGrid.tsx
│   ├── EventCard.tsx
│   ├── SeverityBadge.tsx
│   ├── LiveFeed.tsx           # WebSocket-driven realtime updates
│   └── ChatWindow.tsx
├── lib/
│   └── supabaseClient.ts
└── next.config.js
```

- Realtime updates via WebSocket (`/ws/live`) or Supabase Realtime subscriptions directly on `incidents`.
- Chat UI hits `POST /chat`, streams response.
- Streamlit remains available as a lightweight internal/demo dashboard for quick iteration before the Next.js app is ready.

---

## 12. Deployment Architecture

```
┌───────────────────┐        HTTPS/WSS        ┌───────────────────┐
│  Netlify           │◀───────────────────────▶│  Render             │
│  (Next.js frontend)│                          │  (FastAPI + Agents) │
└───────────────────┘                          └─────────┬──────────┘
                                                            │
                                                            │ Postgres wire protocol
                                                            ▼
                                                  ┌───────────────────┐
                                                  │  Supabase          │
                                                  │  Postgres+pgvector │
                                                  │  Storage, Auth     │
                                                  └─────────▲──────────┘
                                                            │ HTTPS (event push)
┌───────────────────┐                                      │
│  Edge / On-Prem     │──────────────────────────────────────┘
│  CV Pipeline         │
│  (GPU box / NUC)      │
└───────────────────┘
```

- **Netlify:** static/SSR hosting for the Next.js dashboard, auto-deploy from `main`.
- **Render:** web service for FastAPI + LangGraph agents, plus a **Render Cron Job** for the daily/weekly Report Agent.
- **Supabase:** managed Postgres (with pgvector), Storage (snapshots/clips), Auth (dashboard users), and Realtime (push events to the frontend).
- **Edge device:** runs the GPU-bound CV pipeline locally (near the cameras) and pushes structured events to Render over HTTPS — no raw video ever leaves the site, which also keeps bandwidth and privacy exposure low.

### Docker Setup
```
docker/
├── docker-compose.yml
├── backend.Dockerfile
├── edge-cv.Dockerfile
└── nginx.conf
```
- `edge-cv` container: OpenCV + YOLO + InsightFace + DeepSORT, GPU passthrough, run locally.
- `backend` container: FastAPI + LangGraph, deployed to Render (or run via `docker-compose` for local dev).
- `nginx`: reverse proxy for local multi-service dev only; Render/Netlify handle this in production.

---

## 13. Confidence Thresholds & Alerting Rules

| Signal | Threshold | Behavior below threshold |
|---|---|---|
| Face recognition confidence | < 0.6 | Treated as "unknown", not auto-dismissed |
| Detection confidence (YOLO) | < 0.5 | Event discarded, not logged |
| Notification trigger | severity ≥ WARNING **and** confidence ≥ 0.7 | Log only, no notification |
| Escalation (CRITICAL) | severity == CRITICAL **or** flagged detection_type in {weapon, fire, smoke} | Always notify immediately, bypass batching |
| Duplicate suppression | same track_id/camera within 60s | Ignored, merged into existing incident |

---

## 14. Roadmap

**Phase 1 — MVP**
- Live stream ingestion, person/face detection, recognition, event logging, screenshots, Supabase schema live.

**Phase 2 — Agentic Decisions**
- LangGraph multi-agent pipeline, severity classification, confidence-gated notifications (Telegram first).

**Phase 3 — Natural Language Interface**
- pgvector-backed RAG, chat endpoint, dashboard chat UI, daily/weekly automated reports.

**Phase 4 — Advanced Detection**
- Weapon, fire/smoke, PPE, vehicle + license plate, crowd, fall, and violence detection modules — all feeding the same `Event` schema.

**Phase 5 — Multi-Camera Identity Tracking (Stretch Goal)**
- Cross-camera re-identification (same person across Gate-1 → Lobby → Hallway).
- Long-term identity graphs and per-person visit history.
- Automated daily security reports generated and emailed without manual trigger.
- Adaptive alert suppression that learns which patterns are normal per site to reduce false alarms over time.

---

## 15. Folder Structure (Full Repo)

```
cctv-agent/
├── backend/
│   ├── app/
│   │   ├── vision/
│   │   ├── agent/
│   │   ├── memory/
│   │   ├── events/
│   │   ├── api/
│   │   ├── notifications/
│   │   └── websocket/
│   ├── tests/
│   └── Dockerfile
├── edge-cv/
│   ├── capture/
│   ├── detection/
│   ├── tracking/
│   ├── recognition/
│   └── event_client.py
├── frontend/
│   ├── app/
│   ├── components/
│   └── lib/
├── database/
│   └── schema.sql
├── docker/
│   ├── docker-compose.yml
│   ├── backend.Dockerfile
│   └── edge-cv.Dockerfile
├── docs/
│   └── AGENT.md   ← this file
└── README.md
```

---

## 16. Summary of What Changed From the Original Draft

- SQLite + ChromaDB → **Supabase Postgres + pgvector** (single database for relational + vector data).
- Added an explicit **five-agent LangGraph workflow** instead of one generic "agent" step.
- Added **confidence thresholds** at both the detection layer and the notification layer.
- Split memory into **short-term (active incident)** and **long-term (historical, embedded)** tiers.
- Added a **severity classification layer** (INFO/WARNING/CRITICAL) before any notification decision.
- Defined a concrete **deployment split**: edge (CV) vs. Render (agents/API) vs. Netlify (dashboard) vs. Supabase (data/storage/realtime/auth).
- Added full **DB schema, ER diagram, sequence diagrams, API spec, and agent prompts** for direct implementation.

---

## 17. Implementation Status (built so far)

> Keep this in sync with the code. Checked = implemented and verified by the last session.

### Backend agent layer — DONE
- [x] `app/config.py` — agent/LLM/notification config knobs (`FR_DB_PATH`, `FR_EVENT_QUEUE_MAX`, `FR_LLM_*`, channel tokens, …).
- [x] `app/db/store.py` — local-first SQLite store (`agent.db`); schema mirrors the Supabase tables in `database/schema.sql`. Gracefully no-ops if Supabase env is set (kept for swap-in).
- [x] `database/schema.sql` — Supabase Postgres + pgvector DDL drop-in (cameras, faces, users, events, event_embeddings, incidents, alerts, conversations, logs).
- [x] `app/memory/short_term.py` — TTL-based in-process cache (default 3600s).
- [x] `app/memory/long_term.py` — FAISS text-embedding store for past-event RAG (deterministic bag-of-words fallback; langchain embeddings when installed).
- [x] `app/agent/` — perception, severity, reasoning, memory, notifier, report + `graph.py` orchestrator. Runs a sequential async pipeline by default; uses LangGraph when `requirements-agent.txt` is installed.
- [x] `app/events/bus.py` — asyncio event queue + background agent worker.
- [x] `app/notifications/` — Telegram, Email, Slack, Discord; stdlib-only, gracefully no-op when channels are unconfigured.
- [x] `app/api/router.py` — `/incidents`, `/incidents/{id}/report`, `/alert`, `/summary`, `/chat`, `/faces`.
- [x] `app/events/router.py` — `POST/GET /events`; enqueues into the agent pipeline and returns immediately.
- [x] `app/websocket/realtime.py` — `/ws/live` pushes new events/incidents to the dashboard.
- [x] `app/models.py` — API schemas (events, incidents, decisions, chat, summary).
- [x] `app/main.py` — wires routers + event bus startup/shutdown.

### Edge CV worker — DONE
- [x] `edge-cv/main.py` — captures webcam/RTSP/video file, reuses backend detector + matcher, recognizes, POSTs structured events. Run `python edge-cv/main.py`.

### Docker — DONE
- [x] `docker/docker-compose.yml`, `docker/edge-cv.Dockerfile`, `docker/nginx.conf` (dev proxy). Backend Dockerfile lives at `backend/Dockerfile`.

### Frontend — DONE
- [x] `src/hooks/useAgentApi.ts` — client for incidents/report/alert/chat/summary/faces.
- [x] `src/components/tabs/` — Incidents, Faces, Chat, Settings tabs.
- [x] `src/App.tsx` — tab navigation (SCAN / INCIDENTS / FACES / CHAT / SETTINGS) wrapping the existing scan stage.

### Run it
```bash
cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload   # backend :8000
cd frontend && npm run dev                                            # dashboard :5173
python edge-cv/main.py --source 0 --backend http://localhost:8000     # optional edge worker
```

### Notes / next steps
- Install `backend/requirements-agent.txt` (langgraph, langchain) to switch the pipeline to a real StateGraph. The sequential fallback is used otherwise (already verified).
- Optional LLM reasoning via `FR_LLM_*` env (OpenAI-compatible). Deterministic rule-based reasoning is the default when unset — no network needed.
- Notifications deliver only when channel env vars are set (`FR_TELEGRAM_BOT_TOKEN`, etc.).
- Supabase is still the production target; `db/store.py` keeps an explicit `_use_supabase()` escape hatch but the default is local SQLite + FAISS.
