import { useCallback, useEffect, useRef, useState } from "react";
import { useFaceRecognition } from "../hooks/useFaceRecognition";
import type { FaceResult, VideoResponse } from "../types";
import FaceBoxOverlay, { type BoxState } from "./FaceBoxOverlay";
import IdentityPanel, { type PanelItem } from "./IdentityPanel";
import ScanLine from "./ScanLine";
import UnknownFacePrompt from "./UnknownFacePrompt";

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

/** Coarse key for deduplicating prompts for the "same" unknown face across frames. */
const faceKey = (r: FaceResult): string => {
  const [x1, y1, x2, y2] = r.bbox;
  return `${Math.round(x1 / 40)}:${Math.round(y1 / 40)}:${Math.round(x2 / 40)}:${Math.round(y2 / 40)}`;
};

/**
 * Crop the face region out of the current media element so it can be offered
 * as the enrollment photo. bbox is in source pixels (naturalWidth/videoWidth).
 */
function cropFaceRegion(
  media: HTMLImageElement | HTMLVideoElement | null,
  bbox: [number, number, number, number]
): Promise<File | null> {
  if (!media) return Promise.resolve(null);
  const srcW = media instanceof HTMLVideoElement ? media.videoWidth : media.naturalWidth;
  const srcH = media instanceof HTMLVideoElement ? media.videoHeight : media.naturalHeight;
  if (!srcW || !srcH) return Promise.resolve(null);

  const [x1, y1, x2, y2] = bbox;
  // Expand the crop slightly around the face so the enrollment photo isn't a tight ring.
  const padX = (x2 - x1) * 0.15;
  const padY = (y2 - y1) * 0.15;
  const sx = Math.max(0, x1 - padX);
  const sy = Math.max(0, y1 - padY);
  const sw = Math.min(srcW - sx, x2 + padX - sx);
  const sh = Math.min(srcH - sy, y2 + padY - sy);
  if (sw <= 0 || sh <= 0) return Promise.resolve(null);

  const canvas = document.createElement("canvas");
  canvas.width = Math.round(sw);
  canvas.height = Math.round(sh);
  const ctx = canvas.getContext("2d");
  if (!ctx) return Promise.resolve(null);
  ctx.drawImage(media, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);

  return new Promise((resolve) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        resolve(null);
        return;
      }
      resolve(new File([blob], "unknown-face.jpg", { type: "image/jpeg" }));
    }, "image/jpeg");
  });
}

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
  const [rescanKey, setRescanKey] = useState(0);
  const [resultDone, setResultDone] = useState(false);
  const [autoReturnIn, setAutoReturnIn] = useState<number | null>(null);
  const stayRef = useRef(false);
  const [prompt, setPrompt] = useState<{
    key: string;
    face: FaceResult;
    crop: File | null;
    full: File | null;
  } | null>(null);
  const promptedKeysRef = useRef<Set<string>>(new Set());

  const videoRef = useRef<HTMLVideoElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const liveGenRef = useRef(0);
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
        // Invalidate any in-flight getUserMedia of this generation so a stale
        // promise can't overwrite the ref (StrictMode remount) — and kill the
        // camera once, here, so it's always released on the way out.
        liveGenRef.current += 1;
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        disconnect();
        setLiveOn(false);
      };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, file]);

  async function startLive() {
    const gen = liveGenRef.current;
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      // A newer generation was started (or we unmounted) meanwhile — release
      // this stream and don't touch shared state with stale data.
      if (gen !== liveGenRef.current) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      streamRef.current = stream;
      setLiveOn(true);
      connect(handleLiveResult, (e) => setError(e));
    } catch (e) {
      if (gen === liveGenRef.current) setError("Camera access denied or unavailable.");
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
          if (!cancelled) {
            setFaces(
              res.faces.map((f) => ({
                ...bboxToBox(f.bbox, dim?.w ?? f.bbox[2] + 1, dim?.h ?? f.bbox[3] + 1),
                state: stateFor(f),
                result: f,
              }))
            );
            setResultDone(true);
          }
        }, 550);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Recognition failed.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mode, file, recognizeImage, rescanKey]);

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
        setResultDone(true);
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

  // ---------------- auto-return to home ----------------
  // Once a scan task completes, send the operator back to the landing screen
  // so the system restarts cleanly for the next task — no reload needed.
  useEffect(() => {
    if (mode === "live" || !resultDone || prompt || stayRef.current) return;
    setAutoReturnIn(6);
    const id = setInterval(() => {
      setAutoReturnIn((n) => {
        if (n === null) return n;
        if (n <= 1) {
          clearInterval(id);
          onBack();
          return null;
        }
        return n - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [mode, resultDone, prompt, onBack]);

  // ---------------- unknown-face prompt ----------------
  // Whenever an unrecognized face appears, ask the operator if they know it.
  // Each quantized face is only asked once per scan session.
  useEffect(() => {
    if (prompt || faces.length === 0) return;
    const pending = faces.filter((f) => !f.result.matched);
    if (pending.length === 0) return;
    const target = pending.reduce((a, b) => (a.result.score > b.result.score ? a : b));
    const key = faceKey(target.result);
    if (promptedKeysRef.current.has(key)) return;
    promptedKeysRef.current.add(key);
    const media = mode === "image" ? imgRef.current : videoRef.current;
    cropFaceRegion(media, target.result.bbox).then((crop) => {
      frameToFile(media).then((full) => {
        setPrompt({ key, face: target.result, crop, full });
      });
    });
  }, [faces, prompt, mode]);

  const handleEnrolled = useCallback(() => {
    // Re-scan a still image so the freshly enrolled face flips to green.
    if (mode === "image") setRescanKey((k) => k + 1);
  }, [mode]);

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

      {autoReturnIn !== null && (
        <div className="auto-return-banner">
          SCAN COMPLETE — RETURNING TO HOME IN {autoReturnIn}s
          <button
            className="btn ghost small"
            onClick={() => {
              stayRef.current = true;
              setAutoReturnIn(null);
            }}
          >
            STAY
          </button>
        </div>
      )}

      {prompt && (
        <UnknownFacePrompt
          key={prompt.key}
          face={prompt.face}
          cropFile={prompt.crop}
          fullFile={prompt.full}
          bbox={prompt.face.bbox}
          onEnrolled={handleEnrolled}
          onClose={() => setPrompt(null)}
        />
      )}
    </div>
  );
}

function dimFromImage(img: HTMLImageElement | null): { w: number; h: number } | null {
  return img && img.naturalWidth ? { w: img.naturalWidth, h: img.naturalHeight } : null;
}

/** Capture the full current frame (image or video) as a JPEG File for enrollment. */
function frameToFile(media: HTMLImageElement | HTMLVideoElement | null): Promise<File | null> {
  if (!media) return Promise.resolve(null);
  const srcW = media instanceof HTMLVideoElement ? media.videoWidth : media.naturalWidth;
  const srcH = media instanceof HTMLVideoElement ? media.videoHeight : media.naturalHeight;
  if (!srcW || !srcH) return Promise.resolve(null);
  const canvas = document.createElement("canvas");
  canvas.width = srcW;
  canvas.height = srcH;
  const ctx = canvas.getContext("2d");
  if (!ctx) return Promise.resolve(null);
  ctx.drawImage(media, 0, 0, srcW, srcH);
  return new Promise((resolve) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        resolve(null);
        return;
      }
      resolve(new File([blob], "frame.jpg", { type: "image/jpeg" }));
    }, "image/jpeg");
  });
}
