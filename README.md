# IDENT-SCAN — Face Recognition System with Cinematic UI

A full-stack face recognition system: a Python/FastAPI backend (InsightFace
`buffalo_l` — RetinaFace detection + ArcFace embeddings — plus a FAISS index)
and a React/Vite frontend styled like a spy-thriller facial-recognition HUD
(scan-line sweeps, corner-bracket boxes, glitch/decode identity reveals).
demo = https://github.com/Rokibul1022/face-recognition-computer-vision/blob/master/demo.mp4
```
backend/   FastAPI + InsightFace + FAISS
frontend/  Vite + React + Framer Motion
```

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12, FastAPI, InsightFace (`buffalo_l`), OpenCV, NumPy, FAISS (`faiss-cpu`), onnxruntime-gpu (falls back to CPU), uvicorn |
| Frontend | React 18 (Vite), TypeScript, Framer Motion, hand-rolled SVG/CSS HUD |
| Storage | Flat files (`data/{person_id}.png` + `data/{person_id}.json`) behind a `PersonRepository` interface — swap for Postgres without touching detection/matching |

---

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# CPU
pip install -r requirements.txt

# GPU (CUDA + cuDNN present) — replaces onnxruntime with onnxruntime-gpu
pip install -r requirements.txt -r requirements-gpu.txt
```

First run downloads the `buffalo_l` model pack (~275 MB) into `backend/models/`.

Enroll the example gallery and serve:

```bash
python scripts/populate_data.py   # (optional) re-copy images/+info/ into data/
python scripts/build_gallery.py   # build gallery.index + gallery_meta.json

uvicorn app.main:app --reload --port 8000
```

API: `http://localhost:8000/docs`

> **GPU note:** the app auto-selects CUDA when `onnxruntime-gpu` can load its
> CUDA runtime (cuBLAS/cuDNN). On Windows, if you have PyTorch's CUDA build
> installed but no standalone CUDA toolkit, the app finds `torch/lib` and adds
> it to the DLL search path automatically. Override with `FR_CUDA_LIB_DIR`.
> If CUDA can't actually be used it logs a warning and runs on CPU — it never
> silently misreports.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Copy `.env.example` to `.env.local` to point at a
different backend. The app defaults to `http://localhost:8000` for REST and
`ws://localhost:8000` for the live WebSocket scan.

---

## Using the app

There are three scan modes. All three handle **multiple faces per frame** —
every detected face gets its own corner-bracket box (green = matched,
red = no-match), and the side panel lists one identity card per matched face
plus a single "NO MATCH FOUND" card when any face is unidentified.

### Images — multiple faces per frame

- Drag & drop (or click to browse) any image: `.jpg .jpeg .png .jfif .webp .bmp`.
- The backend returns **all** detected faces (not just the largest), each with
  its bounding box, 106-point landmarks and match result.
- Sequence per face: cyan brackets while scanning → amber "matching" flash →
  green + identity card on match, or red + "NO MATCH FOUND" card.
- A group photo with 3 known people → 3 green boxes + 3 identity cards.

> **Face-size limit:** the detector works at 640px, so very small / distant
> faces in a wide group shot can be missed. Faces above roughly 60px wide are
> reliably found; for best results keep faces reasonably large and facing the
> camera.

### Videos — all working

- Drag & drop a video (`.mp4 .avi .mov .mkv .webm`).
- The backend samples frames (every 5th by default, ~2 fps) and returns a
  timestamped timeline of detections.
- The frontend plays the video and **interpolates box positions between
  sampled frames**, so boxes track smoothly even at the low sample rate.
- Multiple faces per frame work exactly like images — one box + identity card
  per person, held green while they stay matched.
- Use the scrubber to jump anywhere; boxes snap to the nearest timeline entry.

### Live scan — webcam / phone camera

- Click **Start Live Scan** — the browser opens your webcam via `getUserMedia`
  and streams JPEG frames over the WebSocket at ~4 fps (~250 ms/frame round
  trip on a GPU backend).
- A matched identity **holds its green box + identity card** instead of
  re-revealing every frame; when the person leaves the frame, the box fades
  out after ~2 seconds.
- "NO MATCH FOUND" appears for unknown faces.

**Using your phone as the camera** (two ways):

1. **Phone-as-PC-webcam (easiest, no changes needed).** Install
   DroidCam, Iriun Webcam or IP Webcam on your phone. Run the companion app on
   the PC (DroidCam/Iriun) or use IP Webcam over the LAN — the phone then
   shows up as a **normal webcam device on the PC**, so the browser picks it
   up automatically. Just start the app and choose it as the camera source.

2. **Run the UI directly on the phone.** `getUserMedia` only works in a
   *secure context* — `localhost` counts, but a phone can't reach your PC's
   `localhost`. Expose the dev server over HTTPS or a tunnel:
   - Run the frontend with `vite --host` so it's reachable on your LAN
     (`http://<PC-LAN-IP>:5173`), and
   - tunnel the backend through HTTPS, e.g.
     `cloudflared tunnel --url http://localhost:8000`
   - set `VITE_API_BASE` / `VITE_WS_BASE` to the tunnel URLs, then open the
     frontend URL on the phone and allow camera access.

   Phone camera quality is fine — the detector and matcher are resolution
   agnostic; just hold the face still a moment for the identity to resolve.

---

## API

| Endpoint | Purpose |
|---|---|
| `POST /enroll` | Upload an image + JSON metadata form fields; stores the photo and rebuilds the gallery |
| `POST /recognize/image` | Detect + match all faces in an uploaded image |
| `POST /recognize/video` | Sample a video (every Nth frame), returns a timestamped timeline of detections |
| `GET /ws/recognize` | WebSocket live scan: send `{"frame":"<base64-jpeg>"}`, receive per-frame `{faces:[...]}` |
| `GET /gallery` | Enrolled identity ids + gallery size |
| `GET /health` | Liveness + gallery size |

Response shape (image):
```json
{
  "faces": [
    {
      "bbox": [74, 78, 184, 235],
      "landmarks": [[130, 236], ...],
      "match": { "person_id": "rakib", "score": 0.71,
                 "info": { "name": "Rakib", "nid": "5993561321", "age": 30,
                           "address": "House 14, Road 11, Tejgaon, Dhaka",
                           "number": "01596977837" } },
      "matched": true
    },
    { "bbox": [...], "matched": false, "score": 0.22 }
  ],
  "processing_ms": 84
}
```

Config knobs (env vars, see `backend/.env.example`):

| Var | Default | Meaning |
|---|---|---|
| `FR_MATCH_THRESHOLD` | `0.45` | Min cosine similarity for a match |
| `FR_DETECT_THRESHOLD` | `0.5` | Detector confidence threshold |
| `FR_VIDEO_SAMPLE_EVERY` | `5` | Recognize every Nth video frame (~2 fps) |
| `FR_CUDA_LIB_DIR` | auto | CUDA runtime DLL directory |

---

## Threshold tuning

```bash
cd backend
python scripts/threshold_tuning.py
```

Reports same-person vs different-person similarity distributions from your
enrollment data so you can pick a threshold that separates them. With the
included example gallery, genuine matches sit near ~1.0 (same source photo)
and impostors are well below `0.45`.

---

## Project layout

```
backend/
  app/
    main.py            # FastAPI app + all routes + WebSocket
    config.py          # env-tunable settings
    detector.py        # InsightFace wrapper (detect/embed), CUDA probe
    repository.py      # flat-file person store (swappable interface)
    matcher.py         # FAISS IndexFlatIP + metadata map, disk cache
    service.py         # detect → embed → match per request
    models.py          # API contract models
    validation.py      # content-sniffed upload validation (no extension gating)
    logging_setup.py   # structured JSON logs w/ request id + stage timings
  scripts/
    populate_data.py   # images/+info/ → data/ as PNG + JSON
    build_gallery.py   # rebuild FAISS index from data/
    threshold_tuning.py
  data/                # enrolled identities (PNG photo + JSON metadata)
  requirements.txt / requirements-gpu.txt
  Dockerfile
  .env.example

frontend/
  src/
    hooks/
      useFaceRecognition.ts     # REST + WebSocket (components stay presentational)
      usePrefersReducedMotion.ts
    components/
      UploadPanel.tsx           # drag-drop + live scan + enroll form
      ScanStage.tsx             # image / video / live feed + overlay container
      FaceBoxOverlay.tsx        # corner brackets + color state machine
      ScanLine.tsx              # looping sweep
      IdentityPanel.tsx         # glitch/decode-in identity reveal
      ConfidenceMeter.tsx       # animated similarity %
    App.tsx
```

---

## Notes

- **PII / `.gitignore`:** enrollment data (`data/`, `gallery.index`,
  `gallery_meta.json`, `.env`) is PII and excluded from git — see
  `backend/.gitignore`. The bundled example identities use fake
  names/NID/address/phone numbers.
- **Source photos:** the `images/` + `info/` folders at the repo root contain
  real face photos and personal metadata (NID, phone, address) and are
  **excluded from version control** (root `.gitignore`). They are local-only
  inputs to `scripts/populate_data.py`; the committed `data/` gallery is
  separate and fake.
- **Multi-photo enrollment:** embeddings are averaged across all of a person's
  photos at gallery build time, because single-photo galleries are the main
  cause of false negatives. Add 2–3 photos per person for reliable matching.
- **Multiple faces:** images, videos and live mode all return and render every
  face in a frame — one bracket + one identity card per matched person, plus a
  "NO MATCH FOUND" card for anyone unidentified.
- **Video smoothness:** boxes are interpolated between the backend's sampled
  frames so tracking doesn't look jittery at ~2 fps.
- **Live mode** streams webcam frames at ~4 fps over the WebSocket; matched
  identities hold their green box + panel rather than re-revealing every
  frame, and boxes fade ~2 s after a face leaves.
- **Accessibility:** all decorative motion honors `prefers-reduced-motion`.
