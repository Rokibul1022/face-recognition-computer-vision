"""Local-first persistent store (SQLite) for the agent layer.

Mirrors the Supabase schema in `database/schema.sql` (cameras, faces, users,
events, event_embeddings, incidents, alerts, conversations, logs) so swapping
to Supabase later is a backend swap, not a code change. Embeddings are stored
as blob columns and queried via the `long_term` FAISS index rather than pgvector
here; the schema file documents the pgvector equivalent.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .. import config

logger = logging.getLogger(__name__)

_SCHEMA = """
create table if not exists cameras (
  id            text primary key,
  name          text not null,
  location      text,
  zone          text,
  active        integer default 1
);

create table if not exists faces (
  id                text primary key,
  full_name         text,
  role              text,
  reference_img_url text,
  created_at        text default (datetime('now'))
);

create table if not exists users (
  id          text primary key,
  email       text unique,
  phone       text,
  telegram_id text,
  role        text default 'viewer'
);

create table if not exists events (
  id                    text primary key,
  camera_id             text,
  track_id              integer,
  identity_face_id      text,
  identity_label        text,
  identity_confidence   real,
  detection_type        text,
  bbox                  text,
  duration_in_frame_sec real,
  snapshot_url          text,
  raw_payload           text,
  created_at            text default (datetime('now'))
);

create table if not exists event_embeddings (
  id          text primary key,
  event_id    text references events(id) on delete cascade,
  description text,
  embedding   blob,
  created_at  text default (datetime('now'))
);

create table if not exists incidents (
  id                    text primary key,
  event_id              text references events(id),
  severity              text check (severity in ('INFO','WARNING','CRITICAL')),
  action                text check (action in ('notify','log_only','ignore','escalate')),
  reasoning             text,
  reference_incident_id text references incidents(id),
  resolved              integer default 0,
  created_at            text default (datetime('now'))
);

create table if not exists alerts (
  id          text primary key,
  incident_id text references incidents(id),
  channel     text,
  recipient   text,
  status      text default 'pending',
  sent_at     text,
  created_at  text default (datetime('now'))
);

create table if not exists conversations (
  id         text primary key,
  user_id    text,
  role       text check (role in ('user','assistant')),
  content    text,
  created_at text default (datetime('now'))
);

create table if not exists logs (
  id         text primary key,
  level      text,
  source     text,
  message    text,
  created_at text default (datetime('now'))
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


class AgentStore:
    """SQLite-backed store for events, incidents, alerts and conversations."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = str(path or config.DB_PATH)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            conn.execute("insert or ignore into cameras (id, name) values ('gate-1', 'Gate 1')")
            conn.commit()
        logger.info("Agent store ready at %s", self.path)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # --- log ----------------------------------------------------------------
    def log(self, level: str, source: str, message: str) -> None:
        try:
            with self._tx() as conn:
                conn.execute(
                    "insert into logs (id, level, source, message) values (?, ?, ?, ?)",
                    (_new_id(), level, source, message),
                )
        except Exception:
            pass  # logging must never crash the pipeline

    def list_logs(self, limit: int = 200) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from logs order by created_at desc limit ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # --- events -------------------------------------------------------------
    def create_event(self, event: dict) -> str:
        event_id = event.get("id") or _new_id()
        with self._tx() as conn:
            conn.execute(
                """
                insert into events (id, camera_id, track_id, identity_face_id,
                  identity_label, identity_confidence, detection_type, bbox,
                  duration_in_frame_sec, snapshot_url, raw_payload)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    event.get("camera_id"),
                    event.get("track_id"),
                    event.get("identity_face_id"),
                    event.get("identity_label"),
                    event.get("identity_confidence"),
                    event.get("detection_type", "person"),
                    json.dumps(event.get("bbox", [])),
                    event.get("duration_in_frame_sec"),
                    event.get("snapshot_url"),
                    json.dumps(event.get("raw_payload") or {}),
                ),
            )
        return event_id

    def get_event(self, event_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("select * from events where id = ?", (event_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_event(row)

    def list_events(
        self,
        *,
        camera_id: str | None = None,
        identity: str | None = None,
        detection_type: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        sql = "select * from events where 1=1"
        args: list[Any] = []
        if camera_id:
            sql += " and camera_id = ?"
            args.append(camera_id)
        if identity:
            sql += " and identity_label = ?"
            args.append(identity)
        if detection_type:
            sql += " and detection_type = ?"
            args.append(detection_type)
        sql += " order by created_at desc limit ?"
        args.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [self._row_to_event(r) for r in rows]

    def count_events(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("select count(*) from events").fetchone()[0])

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> dict:
        d = dict(row)
        try:
            d["bbox"] = json.loads(d.get("bbox") or "[]")
        except json.JSONDecodeError:
            d["bbox"] = []
        try:
            d["raw_payload"] = json.loads(d.get("raw_payload") or "{}")
        except json.JSONDecodeError:
            d["raw_payload"] = {}
        return d

    # --- embeddings (event_embeddings) -------------------------------------
    def save_embedding(self, event_id: str, description: str, embedding: bytes) -> None:
        with self._tx() as conn:
            conn.execute(
                "insert into event_embeddings (id, event_id, description, embedding) values (?, ?, ?, ?)",
                (_new_id(), event_id, description, embedding),
            )

    # --- incidents ----------------------------------------------------------
    def create_incident(self, incident: dict) -> str:
        incident_id = incident.get("id") or _new_id()
        with self._tx() as conn:
            conn.execute(
                """
                insert into incidents (id, event_id, severity, action, reasoning,
                  reference_incident_id, resolved)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident_id,
                    incident.get("event_id"),
                    incident.get("severity"),
                    incident.get("action"),
                    incident.get("reasoning"),
                    incident.get("reference_incident_id"),
                    1 if incident.get("resolved") else 0,
                ),
            )
        return incident_id

    def list_incidents(
        self,
        *,
        severity: str | None = None,
        resolved: bool | None = None,
        limit: int = 200,
    ) -> list[dict]:
        sql = "select * from incidents where 1=1"
        args: list[Any] = []
        if severity:
            sql += " and severity = ?"
            args.append(severity)
        if resolved is not None:
            sql += " and resolved = ?"
            args.append(1 if resolved else 0)
        sql += " order by created_at desc limit ?"
        args.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def get_incident(self, incident_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("select * from incidents where id = ?", (incident_id,)).fetchone()
        return dict(row) if row else None

    def resolve_incident(self, incident_id: str) -> bool:
        with self._tx() as conn:
            cur = conn.execute(
                "update incidents set resolved = 1 where id = ?", (incident_id,)
            )
        return cur.rowcount > 0

    # --- alerts -------------------------------------------------------------
    def create_alert(self, incident_id: str, channel: str, recipient: str, status: str = "pending") -> None:
        with self._tx() as conn:
            conn.execute(
                "insert into alerts (id, incident_id, channel, recipient, status) values (?, ?, ?, ?, ?)",
                (_new_id(), incident_id, channel, recipient, status),
            )

    # --- conversations -------------------------------------------------------
    def append_conversation(self, role: str, content: str, user_id: str = "anonymous") -> None:
        with self._tx() as conn:
            conn.execute(
                "insert into conversations (id, user_id, role, content) values (?, ?, ?, ?)",
                (_new_id(), user_id, role, content),
            )

    def list_conversations(self, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from conversations order by created_at desc limit ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]