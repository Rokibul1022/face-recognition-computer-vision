"""Dashboard API: incidents, alerts, summary, chat, faces, gallery."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from ..agent.report import ReportAgent
from ..db.store import AgentStore
from ..memory.long_term import LongTermMemory
from ..models import (
    AlertIn,
    ChatIn,
    ChatOut,
    EnrollResponse,
    FaceDetail,
    FaceResult,
    FaceUpdate,
    GalleryStatus,
    IncidentOut,
    IncidentReport,
    SummaryOut,
)
from ..notifications import dispatch
from .chat import build_chat_reply

logger = logging.getLogger(__name__)


def build_api_router(store: AgentStore, long_term: LongTermMemory, repo, matcher, service) -> APIRouter:
    """Compose the dashboard router. `plain` flag disables LLM w/o breaking imports."""
    report = ReportAgent(store)
    router = APIRouter(tags=["dashboard"])

    # --- incidents -----------------------------------------------------------
    @router.get("/incidents", response_model=list[IncidentOut])
    async def list_incidents(
        severity: str | None = Query(None, pattern="^(INFO|WARNING|CRITICAL)$"),
        resolved: bool | None = Query(None),
        limit: int = Query(200, le=5000),
    ) -> list[IncidentOut]:
        return [
            IncidentOut(
                id=r["id"],
                event_id=r.get("event_id"),
                severity=r["severity"],
                action=r["action"],
                reasoning=r.get("reasoning") or "",
                reference_incident_id=r.get("reference_incident_id"),
                resolved=bool(r.get("resolved")),
                created_at=r.get("created_at") or "",
            )
            for r in store.list_incidents(severity=severity, resolved=resolved, limit=limit)
        ]

    @router.post("/incidents/{incident_id}/resolve")
    async def resolve_incident(incident_id: str) -> dict:
        ok = store.resolve_incident(incident_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Incident not found.")
        return {"id": incident_id, "resolved": True}

    @router.get("/incidents/{incident_id}/report", response_model=IncidentReport)
    async def get_incident_report(incident_id: str) -> IncidentReport:
        data = report.report_for_incident(incident_id)
        if not data:
            raise HTTPException(status_code=404, detail="Incident not found.")
        return IncidentReport(**data)

    # --- alerts / summary ----------------------------------------------------
    @router.post("/alert")
    async def trigger_alert(alert: AlertIn) -> dict:
        """Manually trigger an alert through the configured channels."""
        results = dispatch.send_all(
            alert.message,
            subject=f"MANUAL ALERT {alert.severity}",
            severity=alert.severity,
            override_bypass=True,
        )
        sent = [k for k, v in results.items() if v]
        return {"channels": results, "delivered": sent}

    @router.get("/summary", response_model=SummaryOut)
    async def generate_summary(window: int = Query(86400, le=604800)) -> SummaryOut:
        data = report.summary(window_seconds=window)
        return SummaryOut(**data)

    # --- chat ----------------------------------------------------------------
    @router.post("/chat", response_model=ChatOut)
    async def chat_endpoint(chat: ChatIn) -> ChatOut:
        store.append_conversation("user", chat.message)
        reply, references = build_chat_reply(chat.message, store, long_term)
        store.append_conversation("assistant", reply)
        return ChatOut(reply=reply, references=references)

    # --- faces / gallery -----------------------------------------------------
    @router.get("/faces", response_model=list[FaceDetail])
    async def list_faces() -> list[FaceDetail]:
        """Every enrolled person (from the repo, not just the matcher) with photo URL."""
        return [
            FaceDetail(**{**rec.to_dict(), "photo_url": f"/faces/{rec.person_id}/photo"})
            for rec in repo.all()
        ]

    @router.get("/faces/{person_id}/photo")
    async def face_photo(person_id: str) -> Response:
        bytes_, mime = repo.photo_bytes(person_id) or (None, "image/png")
        if bytes_ is None:
            raise HTTPException(status_code=404, detail="No photo for this face.")
        return Response(content=bytes_, media_type=mime)

    @router.get("/faces/{person_id}", response_model=FaceDetail)
    async def get_face(person_id: str) -> FaceDetail:
        person = repo.get(person_id)
        if person is None:
            raise HTTPException(status_code=404, detail="Face not found.")
        return FaceDetail(
            person_id=person_id,
            name=person.name,
            nid=person.nid,
            age=person.age,
            address=person.address,
            number=person.number,
            photo_url=f"/faces/{person_id}/photo",
        )

    @router.put("/faces/{person_id}", response_model=FaceDetail)
    async def update_face(person_id: str, payload: FaceUpdate) -> FaceDetail:
        if repo.get(person_id) is None:
            raise HTTPException(status_code=404, detail="Face not found.")
        repo.save_meta(
            person_id,
            {
                "name": payload.name,
                "nid": payload.nid,
                "age": payload.age,
                "address": payload.address,
                "number": payload.number,
            },
        )
        matcher.build_from_repo(repo, force=True)
        return FaceDetail(
            person_id=person_id,
            name=payload.name,
            nid=payload.nid,
            age=payload.age,
            address=payload.address,
            number=payload.number,
            photo_url=f"/faces/{person_id}/photo",
        )

    @router.delete("/faces/{person_id}")
    async def delete_face(person_id: str) -> dict:
        if repo.get(person_id) is None:
            raise HTTPException(status_code=404, detail="Face not found.")
        repo.delete(person_id)
        matcher.build_from_repo(repo, force=True)
        return {"person_id": person_id, "deleted": True}

    @router.get("/gallery-status", response_model=GalleryStatus)
    async def gallery() -> GalleryStatus:
        matcher.ensure(repo)
        return GalleryStatus(enrolled=matcher.ids, size=len(matcher.ids))

    return router