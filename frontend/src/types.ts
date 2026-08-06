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
