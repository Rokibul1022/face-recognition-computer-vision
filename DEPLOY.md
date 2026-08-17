# Deploying your Face Recognition Scanner

Two parts, deployed separately:

| Part | Where | What |
|------|-------|------|
| Backend + agent + chat | Render (Docker) | FastAPI, face recognition, events, memory, LLM chat |
| Frontend UI | Netlify | Vite React app (dist/) |

The **camera watcher** (`edge-cv/main.py`) is NOT deployed — each user runs it
on their own computer against a camera/RTSP feed and points it at your backend.
The hosted backend provides face recognition, enrollment, history, and chat.

---

## 1. Backend image (build locally → push to a registry)

Seed data + model weights are **gitignored**, so they must be baked into an image
locally and pushed to a registry (Docker Hub or GHCR). Render cannot build them
from git.

Prereq: Docker Desktop installed and logged in (`docker login`).

```bash
git push                      # your code + these deploy files
./deploy/build-image.sh ghcr.io/you/ident-backend:seed
```

That produces ~700MB image: your faces (`backend/data`), gallery, `agent.db`,
long-term memory, and the 600MB InsightFace weights baked in — cold starts are
fast and no re-download happens.

## 2. Deploy on Render

Option A — Blueprint (recommended): edit `backend/render.yaml`
(change `image:` to your pushed name), then in Render pick
**New → Blueprint** and point at this repo.

Option B — Dashboard: **New → Web Service → Deploy from container image**,
paste your image name.

Then set env vars (dashboard → your service → Environment):

- `OPENAI_API_KEY` — your Groq key (secret)
- `OPENAI_BASE_URL=https://api.groq.com/openai/v1`
- `FR_LLM_MODEL=allam-2-7b`
- `FR_CORS_ORIGINS=https://<your-site>.netlify.app`
- `FR_MODELS_DIR=/srv/models`

Pick a **paid plan** if you want the persistent disk (survives restarts +
keeps new enrollments/events across redeploys; `disk:` block + `FR_COPY_SEED=1`
in render.yaml seed the disk from the baked copy on first boot). The **free**
plan works too, but state resets on restart and the container spins down after
15 min idle.

## 3. Deploy on Netlify

Dashboard → **Add new site → Import an existing project** → this repo.
Netlify reads `frontend/netlify.toml`: builds `npm run build`, publishes `dist`,
and sets `VITE_API_BASE` to your Render URL. Edit that URL in
`frontend/netlify.toml` before pushing, or set it as an env var in Netlify.

Your site is HTTPS → browser camera (`getUserMedia`) works.

## 4. Verify

- https://<backend>.onrender.com/health → `{"status":"ok","gallery_size": N}`
- https://<backend>.onrender.com/faces → your people list
- https://<site>.netlify.app → enroll/scan/chat

## Security notes

- No auth: anyone with the URL can enroll/delete people. Add an `FR_API_TOKEN`
  middleware check before sharing publicly.
- Set `FR_CORS_ORIGINS` to your exact Netlify URL (not `*`) once deployed.
- Images + names of enrolled people are PII — keep the registry/backend private.