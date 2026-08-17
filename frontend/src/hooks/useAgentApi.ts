import { useCallback } from "react";
import { API_BASE } from "./useFaceRecognition";
import type {
  AgentIncident,
  AlertResult,
  ChatResponse,
  FaceDetail,
  IncidentReport,
  SummaryResponse,
} from "../types";

/**
 * Thin client for the agent-layer endpoints on the backend:
 * incidents / summary / alert / chat / faces. Components stay presentational.
 */
export function useAgentApi() {
  const listIncidents = useCallback(async (limit = 50): Promise<AgentIncident[]> => {
    const res = await fetch(`${API_BASE}/incidents?limit=${limit}`);
    if (!res.ok) throw new Error(await _detail(res));
    return res.json();
  }, []);

  const incidentReport = useCallback(async (incidentId: string): Promise<IncidentReport> => {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/report`);
    if (!res.ok) throw new Error(await _detail(res));
    return res.json();
  }, []);

  const sendAlert = useCallback(
    async (message: string, severity: string): Promise<AlertResult> => {
      const res = await fetch(`${API_BASE}/alert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, severity }),
      });
      if (!res.ok) throw new Error(await _detail(res));
      return res.json();
    },
    []
  );

  const askChat = useCallback(async (message: string): Promise<ChatResponse> => {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    if (!res.ok) throw new Error(await _detail(res));
    return res.json();
  }, []);

  const getSummary = useCallback(async (windowSeconds = 86400): Promise<SummaryResponse> => {
    const res = await fetch(`${API_BASE}/summary?window_seconds=${windowSeconds}`);
    if (!res.ok) throw new Error(await _detail(res));
    return res.json();
  }, []);

  const listFaces = useCallback(async (): Promise<FaceDetail[]> => {
    const res = await fetch(`${API_BASE}/faces`);
    if (!res.ok) throw new Error(await _detail(res));
    return res.json();
  }, []);

  const updateFace = useCallback(
    async (personId: string, data: Omit<FaceDetail, "person_id" | "photo_url">): Promise<FaceDetail> => {
      const res = await fetch(`${API_BASE}/faces/${personId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error(await _detail(res));
      return res.json();
    },
    []
  );

  const deleteFace = useCallback(
    async (personId: string): Promise<void> => {
      const res = await fetch(`${API_BASE}/faces/${personId}`, { method: "DELETE" });
      if (!res.ok) throw new Error(await _detail(res));
    },
    []
  );

  return { listIncidents, incidentReport, sendAlert, askChat, getSummary, listFaces, updateFace, deleteFace };
}

async function _detail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body.detail ?? `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}
