import { useCallback, useEffect, useRef, useState } from "react";
import type {
  RecognitionResponse,
  VideoResponse,
  EnrollResponse,
  FaceResult,
} from "../types";

export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";
export const WS_BASE = (import.meta.env.VITE_WS_BASE as string | undefined) ?? API_BASE.replace(/^http/, "ws");

export type WsStatus = "idle" | "connecting" | "open" | "closed";

/**
 * Owns every network call the UI makes: image/video recognition, enrollment
 * and the live WebSocket scan. Components stay presentational.
 */
export function useFaceRecognition() {
  const wsRef = useRef<WebSocket | null>(null);
  const [wsStatus, setWsStatus] = useState<WsStatus>("idle");

  const recognizeImage = useCallback(
    async (file: File): Promise<RecognitionResponse> => {
      const body = new FormData();
      body.append("image", file);
      const res = await fetch(`${API_BASE}/recognize/image`, {
        method: "POST",
        body,
      });
      if (!res.ok) throw new Error(await _errorDetail(res));
      return res.json();
    },
    []
  );

  const recognizeVideo = useCallback(
    async (file: File): Promise<VideoResponse> => {
      const body = new FormData();
      body.append("video", file);
      const res = await fetch(`${API_BASE}/recognize/video`, {
        method: "POST",
        body,
      });
      if (!res.ok) throw new Error(await _errorDetail(res));
      return res.json();
    },
    []
  );

  const enroll = useCallback(
    async (
      file: File,
      meta: { person_id: string; name: string; nid: string; age: string; address: string; number: string }
    ): Promise<EnrollResponse> => {
      const body = new FormData();
      body.append("image", file);
      body.append("person_id", meta.person_id);
      body.append("name", meta.name);
      body.append("nid", meta.nid);
      body.append("age", meta.age || "0");
      body.append("address", meta.address);
      body.append("number", meta.number);
      const res = await fetch(`${API_BASE}/enroll`, { method: "POST", body });
      if (!res.ok) throw new Error(await _errorDetail(res));
      return res.json();
    },
    []
  );

  const connect = useCallback((onResult: (faces: FaceResult[]) => void, onError: (e: string) => void) => {
    setWsStatus("connecting");
    const ws = new WebSocket(`${WS_BASE}/ws/recognize`);
    wsRef.current = ws;
    ws.onopen = () => setWsStatus("open");
    ws.onclose = () => setWsStatus("closed");
    ws.onerror = () => {
      onError("WebSocket error");
      setWsStatus("closed");
    };
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.error) {
          onError(data.error);
          return;
        }
        onResult(data.faces as FaceResult[]);
      } catch {
        /* ignore malformed frame */
      }
    };
  }, []);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setWsStatus("idle");
  }, []);

  /** Send one JPEG frame to the live scanner. Returns true if it was sent. */
  const sendLiveFrame = useCallback((dataUrl: string): boolean => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify({ frame: dataUrl }));
    return true;
  }, []);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  return { recognizeImage, recognizeVideo, enroll, connect, disconnect, sendLiveFrame, wsStatus };
}

async function _errorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body.detail ?? `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}
