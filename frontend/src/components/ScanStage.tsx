import { useCallback, useEffect, useRef, useState } from "react";
import { useFaceRecognition } from "../hooks/useFaceRecognition";
import type { FaceResult, VideoResponse } from "../types";
import FaceBoxOverlay, { type BoxState } from "./FaceBoxOverlay";
import IdentityPanel, { type PanelItem } from "./IdentityPanel";
import ScanLine from "./ScanLine";

export type ScanMode = "image" | "video" | "live";

interface Props {
  mode: ScanMode;
  file?: File;
  onBack: () => void;
}

type Box = { x: number; y: number; w: number; h: number };

interface DisplayFace extends Box {
  state: BoxState;
  result: FaceResult;
}

const bboxToBox = (bbox: [number, number, number, number], w: number, h: number): Box => ({
  x: bbox[0] / w,
  y: bbox[1] / h,
  w: (bbox[2] - bbox[0]) / w,
  h: (bbox[3] - bbox[1]) / h,
});

const stateFor = (r: FaceResult): BoxState => (r.matched ? "match" : "nomatch");

export default function ScanStage({ mode, file, onBack }: Props) {
  const { recognizeImage, recognizeVideo, connect, disconnect, sendLiveFrame } = useFaceRecognition();

  const [mediaUrl, setMediaUrl] = useState<string | null>(null);
  const [mediaDim, setMediaDim] = useState<{ w: number; h: number } | null>(null);
  const [faces, setFaces] = useState<DisplayFace[]>([]);
  const [processingMs, setProcessingMs] = useState<number | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [videoReady, setVideoReady] = useState(false);
  const [videoTime, setVideoTime] = useState(0);
  const [liveOn, setLiveOn] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timelineRef = useRef<VideoResponse["timeline"]>([]);
  const sustainedRef = useRef<Sustained[]>([]);
  const [, forceTick] = useState(0);

  interface Sustained {
    key: string; // person_id (matched) or `f:<index>`
    result: FaceResult;
    box: Box;
    frames: number; // frames since last seen
    matched: boolean;
  }

  // ---------------- media URL lifecycle ----------------
  useEffect(() => {
    if (file) {
      const url = URL.createObjectURL(file);
      setMediaUrl(url);
      return () => URL.revokeObjectURL(url);
    }
    if (mode === "live") {
      startLive();
      return () => {
        streamRef.current?.getTracks().forEach((t) => t.stop());
        disconnect();
        setLiveOn(false);
      };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, file]);

  async function startLive() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      streamRef.current = stream;
      setLiveOn(true);
      connect(handleLiveResult, (e) => setError(e));
    } catch (e) {
      setError("Camera access denied or unavailable.");
    }
  }

  // Attach the webcam stream to the <video> element once it is mounted.
  useEffect(() => {
    if (mode !== "live" || !liveOn || !videoRef.current) return;
    if (streamRef.current && videoRef.current.srcObject !== streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [mode, liveOn]);

  const handleLiveResult = useCallback((res: FaceResult[]) => {
    const dim = mediaDimRef.current;
    if (!dim) return;
    const now: Sustained[] = [];
    res.forEach((r, i) => {
      const box = bboxToBox(r.bbox, dim.w, dim.h);
      const key = r.matched ? `p:${r.match!.person_id}` : `f:${i}`;
      now.push({ key, result: r, box, frames: 0, matched: r.matched });
    });
    // Age out entries that vanished (grace of ~8 frames ≈ 2s at 4fps).
    for (const old of sustainedRef.current) {
      if (now.some((n) => n.key === old.key)) continue;
      if (old.frames < 8) {
        old.frames += 1;
        now.push(old);
      }
    }
    sustainedRef.current = now;
    setFaces(
      now.map((s) => ({
        ...s.box,
        state: s.matched ? "match" : "nomatch",
        result: s.result,
      }))
    );
    forceTick((t) => t + 1);
  }, []);

  const mediaDimRef = useRef<{ w: number; h: number } | null>(null);
  useEffect(() => {
    mediaDimRef.current = mediaDim;
  }, [mediaDim]);

  // ---------------- live capture loop ----------------
  useEffect(() => {
    if (mode !== "live" || !liveOn) return;
    const canvas = document.createElement("canvas");
    let running = true;
    const tick = () => {
      const v = videoRef.current;
      if (!running) return;
      if (v && v.videoWidth && v.videoHeight) {
        // Capture media dimensions as soon as the stream reports them so
        // boxes can be positioned even if metadata fires late.
        if (!mediaDimRef.current) {
          setMediaDim({ w: v.videoWidth, h: v.videoHeight });
        }
        canvas.width = v.videoWidth;
        canvas.height = v.videoHeight;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.drawImage(v, 0, 0, canvas.width, canvas.height);
          sendLiveFrame(canvas.toDataURL("image/jpeg", 0.6));
        }
      }
    };
    const id = setInterval(tick, 250);
    return () => {
      running = false;
      clearInterval(id);
    };
  }, [mode, liveOn, sendLiveFrame]);

  // ---------------- image mode ----------------
  useEffect(() => {
    if (mode !== "image" || !file) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await recognizeImage(file);
        if (cancelled) return;
        setProcessingMs(res.processing_ms);
        const dim = dimFromImage(imgRef.current);
        if (dim) setMediaDim(dim);
        // Brief amber "matching" phase before the result locks in.
        setFaces(
          res.faces.map((f) => ({
            ...bboxToBox(f.bbox, dim?.w ?? f.bbox[2] + 1, dim?.h ?? f.bbox[3] + 1),
            state: "matching" as BoxState,
            result: f,
          }))
        );
        setTimeout(() => {
          if (!cancelled)
            setFaces(
              res.faces.map((f) => ({
                ...bboxToBox(f.bbox, dim?.w ?? f.bbox[2] + 1, dim?.h ?? f.bbox[3] + 1),
                state: stateFor(f),
                result: f,
              }))
            );
        }, 550);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Recognition failed.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mode, file, recognizeImage]);

  // ---------------- video mode ----------------
  useEffect(() => {
    if (mode !== "video" || !file) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await recognizeVideo(file);
        if (cancelled) return;
        timelineRef.current = res.timeline;
        setProcessingMs(res.processing_ms);
        setVideoReady(true);
        setVideoTime(0);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Video processing failed.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mode, file, recognizeVideo]);

  // Update boxes as the video plays, interpolating between sampled frames.
  useEffect(() => {
    if (mode !== "video" || !videoReady) return;
    const timeline = timelineRef.current;
    const dim = mediaDim;
    if (!dim || timeline.length === 0) return;

    const t = videoTime;
    let prev = timeline[0];
    let next = timeline[timeline.length - 1];
    for (const e of timeline) {
      if (e.timestamp <= t) prev = e;
      else {
        next = e;
        break;
      }
    }
    const span = Math.max(next.timestamp - prev.timestamp, 0.001);
    const ratio = Math.min(Math.max((t - prev.timestamp) / span, 0), 1);

    const render: DisplayFace[] = [];
    prev.faces.forEach((pf, i) => {
      const nf = next.faces[i] ?? pf;
      const x1 = pf.bbox[0] + (nf.bbox[0] - pf.bbox[0]) * ratio;
      const y1 = pf.bbox[1] + (nf.bbox[1] - pf.bbox[1]) * ratio;
      const x2 = pf.bbox[2] + (nf.bbox[2] - pf.bbox[2]) * ratio;
      const y2 = pf.bbox[3] + (nf.bbox[3] - pf.bbox[3]) * ratio;
      render.push({
        ...bboxToBox([x1, y1, x2, y2], dim.w, dim.h),
        state: stateFor(nf),
        result: nf,
      });
    });
    setFaces(render);
  }, [mode, videoReady, videoTime, mediaDim]);

  // ---------------- media dims ----------------
  useEffect(() => {
    if (mode === "image") {
      const img = imgRef.current;
      if (img && img.complete) {
        const d = dimFromImage(img);
        if (d) setMediaDim(d);
      }
    }
    if (mode === "video") {
      const v = videoRef.current;
      if (v && v.videoWidth) setMediaDim({ w: v.videoWidth, h: v.videoHeight });
    }
  }, [mode, mediaUrl, videoReady]);

  // ---------------- panel data ----------------
  // One identity card per MATCHED face; unknown faces collapse into a single
  // "NO MATCH" card (kept out of the way when everyone is identified).
  const matchedFaces = faces.filter((f) => f.result.matched);
  const unmatched = faces.filter((f) => !f.result.matched);
  const items: PanelItem[] = matchedFaces.map((f) => ({
    key: `p:${f.result.match!.person_id}`,
    match: f.result.match,
    score: f.result.score,
  }));
  if (unmatched.length > 0) {
    const top = unmatched.reduce((a, b) =>
      a.result.score > b.result.score ? a : b
    );
    items.push({ key: "NOMATCH", match: null, score: top.result.score });
  }
  const showPanel = mode === "image" || mode === "video" || faces.length > 0;

  const hint = faces.length === 0 ? (error ?? "Acquiring feed…") : null;

  return (
    <div className="scan-stage">
      <div className="media-area">
        <div className="media-frame" style={{ aspectRatio: mediaDim ? `${mediaDim.w} / ${mediaDim.h}` : undefined }}>
          {mode === "image" && mediaUrl && (
            <img
              ref={imgRef}
              src={mediaUrl}
              onLoad={(e) => {
                const t = e.currentTarget;
                setMediaDim({ w: t.naturalWidth, h: t.naturalHeight });
              }}
              alt=""
            />
          )}
          {mode === "video" && mediaUrl && (
            <video
              ref={videoRef}
              src={mediaUrl}
              controls
              playsInline
              onTimeUpdate={(e) => setVideoTime(e.currentTarget.currentTime)}
              onLoadedMetadata={(e) => {
                const v = e.currentTarget;
                setMediaDim({ w: v.videoWidth, h: v.videoHeight });
              }}
            />
          )}
          {mode === "live" && (
            <video ref={videoRef} autoPlay playsInline muted style={{ minWidth: 480, minHeight: 360 }} />
          )}

          <div className="overlay">
            <ScanLine />
            {faces.map((f, i) => (
              <FaceBoxOverlay
                key={mode === "live" ? f.result.match?.person_id ?? `f${i}` : `${i}-${f.result.match?.person_id ?? "x"}`}
                box={f}
                state={f.state}
                label={f.result.match ? f.result.match.person_id.toUpperCase() : undefined}
              />
            ))}
            {hint && (
              <div className="fps-counter" style={{ color: "var(--hud-red)" }}>
                {hint}
              </div>
            )}
          </div>

          {mode === "live" && liveOn && (
            <div className="live-badge">
              <span className="dot" /> LIVE SCAN
            </div>
          )}
          {mode === "live" && (
            <div className="fps-counter">
              {faces.length} FACE{faces.length === 1 ? "" : "S"} · ~4 FPS
            </div>
          )}
        </div>
      </div>

      {showPanel && (
        <IdentityPanel items={items} processingMs={processingMs} />
      )}

      <button
        className="btn danger"
        onClick={onBack}
        style={{ position: "absolute", top: 16, left: 16, zIndex: 10 }}
      >
        ← Abort
      </button>
    </div>
  );
}

function dimFromImage(img: HTMLImageElement | null): { w: number; h: number } | null {
  return img && img.naturalWidth ? { w: img.naturalWidth, h: img.naturalHeight } : null;
}
