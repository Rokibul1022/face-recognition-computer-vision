export interface FaceMatch {
  person_id: string;
  score: number;
  info: {
    name: string;
    nid: string;
    age: number;
    address: string;
    number: string;
  };
}

export interface FaceResult {
  bbox: [number, number, number, number]; // [x1, y1, x2, y2] in source pixels
  landmarks: [number, number][];
  match: FaceMatch | null;
  matched: boolean;
  score: number;
}

export interface RecognitionResponse {
  faces: FaceResult[];
  processing_ms: number;
}

export interface VideoTimelineEntry {
  frame_index: number;
  timestamp: number;
  faces: FaceResult[];
}

export interface VideoResponse {
  timeline: VideoTimelineEntry[];
  total_frames: number;
  processed_frames: number;
  processing_ms: number;
}

export interface EnrollResponse {
  person_id: string;
  photos: number;
  embedded: boolean;
  gallery_size: number;
}

export interface FaceDetail {
  person_id: string;
  name: string;
  nid: string;
  age: number;
  address: string;
  number: string;
  photo_url: string | null;
}

// ---- Agent-layer types (matching backend app/api/models.py) ----

export interface AgentIncident {
  id: string;
  event_id: string;
  severity: "LOW" | "WARNING" | "HIGH" | "CRITICAL";
  action: string;
  reasoning: string;
  reference_incident_id: string | null;
  resolved: boolean;
  created_at: string;
}

export interface IncidentReport {
  id: string;
  incident_id: string;
  format: string;
  summary: string;
  created_at: string;
}

export interface AlertResult {
  channels: Record<string, boolean>;
  delivered: string[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatReference {
  event_id: string;
  description?: string;
  human?: string;
  incident_id: string | null;
  similarity: number;
}

export interface ChatResponse {
  reply: string;
  references: ChatReference[];
}

export interface SummaryResponse {
  generated_at: string;
  window_seconds: number;
  total_events: number;
  incidents: AgentIncident[];
  by_severity: Record<string, number>;
}
