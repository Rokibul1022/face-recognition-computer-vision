"""Face detection + landmark alignment + embedding via InsightFace.

Wraps the `FaceAnalysis` app (`buffalo_l`: RetinaFace detection + ArcFace
embedding) into a small, testable API and exposes the per-face timings that
the structured logging pipeline uses.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from . import config

logger = logging.getLogger(__name__)


def _add_cuda_dll_paths() -> None:
    """Best-effort: surface PyTorch-bundled CUDA/cuDNN DLLs on Windows.

    onnxruntime-gpu ships without the CUDA runtime libs (cublas, cudnn). If a
    PyTorch CUDA build is installed, its `lib` dir already contains a matching
    (cuBLAS + cuDNN) set — expose it so the CUDAExecutionProvider can load.
    Locations probed (first match wins):
      1. FR_CUDA_LIB_DIR env var (explicit override)
      2. `torch/lib` from the importable torch package
      3. `torch/lib` under the current user's site-packages (torch is often
         installed there even when the venv can't import it)
    Harmless if none are found.
    """
    try:
        import os
        import sys

        if sys.platform != "win32":
            return
        import pathlib

        candidates: list[str] = []
        if config.CUDA_LIB_DIR:
            candidates.append(config.CUDA_LIB_DIR)

        try:
            import torch  # type: ignore

            candidates.append(str(pathlib.Path(torch.__file__).parent / "lib"))
        except Exception:
            pass

        try:
            import site

            candidates.append(
                str(
                    pathlib.Path(site.getusersitepackages())
                    / "torch"
                    / "lib"
                )
            )
        except Exception:
            pass

        for cand in candidates:
            lib_dir = pathlib.Path(cand)
            if lib_dir.is_dir():
                # onnxruntime's CUDA provider resolves cuBLAS/cuDNN via PATH on
                # Windows; add_dll_directory alone is insufficient for it.
                path_entries = [str(lib_dir)] + os.environ.get("PATH", "").split(os.pathsep)
                os.environ["PATH"] = os.pathsep.join(
                    dict.fromkeys(e for e in path_entries if e)
                )
                try:
                    os.add_dll_directory(str(lib_dir))
                except (OSError, ValueError):
                    pass
                logger.debug("Added CUDA DLL search path: %s", lib_dir)
                break
    except Exception:
        pass


def _pick_ctx_id() -> int:
    """Return a CUDA device id when it can actually be used, else -1 (CPU).

    `ort.get_available_providers()` over-reports: it lists CUDAExecutionProvider
    even when the cuBLAS/cuDNN runtime DLLs are missing and session creation
    will silently fall back to CPU. To avoid silently falling back, we probe by
    creating a real session on the detection model (once it has been
    downloaded) and log which provider ended up being used.
    """
    _add_cuda_dll_paths()
    try:
        import onnxruntime as ort
    except Exception:
        return -1

    if "CUDAExecutionProvider" not in ort.get_available_providers():
        logger.warning("onnxruntime-gpu not installed — running on CPU.")
        return -1

    # The detection ONNX file may not exist on the very first run; fall back to
    # the provider-list heuristic in that case.
    det_model = config.MODELS_DIR / "models" / config.MODEL_PACK / "det_10g.onnx"
    if det_model.exists():
        try:
            sess = ort.InferenceSession(
                str(det_model),
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            used = sess.get_providers()
            if used and used[0].startswith("CUDA"):
                logger.info("Using CUDAExecutionProvider (GPU) for inference.")
                return 0
            logger.warning(
                "CUDA provider requested but unusable (missing CUDA runtime / "
                "cuDNN DLLs?). Falling back to CPU. Installed providers: %s",
                used,
            )
            return -1
        except Exception as exc:  # pragma: no cover
            logger.warning("CUDA probe failed (%s); falling back to CPU.", exc)
            return -1

    return 0


class _InsightFaceWrapper:
    """Lazy singleton wrapper so importing the module is cheap."""

    def __init__(self) -> None:
        self._app = None

    def _ensure(self):
        if self._app is None:
            logger.info(
                "Initializing InsightFace FaceAnalysis (pack=%s, threshold=%.2f)...",
                config.MODEL_PACK,
                config.DETECTOR_CONF_THRESHOLD,
            )
            try:
                from insightface.app import FaceAnalysis
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "insightface is not installed. Run `pip install -r requirements.txt`."
                ) from exc

            ctx_id = _pick_ctx_id()
            config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
            app = FaceAnalysis(
                name=config.MODEL_PACK,
                root=str(config.MODELS_DIR),
                allowed_modules=["detection", "recognition", "landmark_2d_106"],
            )
            app.prepare(
                ctx_id=ctx_id,  # >= 0 = CUDA device, -1 = CPU
                det_thresh=config.DETECTOR_CONF_THRESHOLD,
                det_size=(640, 640),
            )
            self._app = app
            logger.info("InsightFace model pack '%s' ready on ctx_id=%d.", config.MODEL_PACK, ctx_id)
        return self._app


_facerec = _InsightFaceWrapper()


@dataclass
class DetectedFace:
    bbox: list[float]  # [x1, y1, x2, y2] in image pixel coords
    landmarks: list[list[float]] = field(default_factory=list)
    score: float = 0.0  # detector confidence
    embedding: np.ndarray | None = None  # L2-normalized ArcFace vector
    detect_ms: float = 0.0
    embed_ms: float = 0.0


def detect_faces(
    frame_bgr: np.ndarray,
    embed: bool = True,
) -> list[DetectedFace]:
    """Detect all faces in a BGR frame.

    Returns *every* detected face (not just the largest) with its bbox,
    landmarks and detector confidence. Detections below the configured
    confidence threshold are skipped by InsightFace's `det_thresh`.
    """
    t0 = time.perf_counter()
    app = _facerec._ensure()
    raw = app.get(frame_bgr)
    detect_ms = (time.perf_counter() - t0) * 1000.0

    faces: list[DetectedFace] = []
    for item in raw:
        lmk = getattr(item, "landmark", None) or getattr(item, "landmark_2d_106", None)
        face = DetectedFace(
            bbox=[float(v) for v in item.bbox],
            landmarks=(
                [[float(x), float(y)] for x, y in lmk]
                if lmk is not None
                else []
            ),
            score=float(item.det_score),
        )
        if embed:
            t1 = time.perf_counter()
            face.embedding = item.normed_embedding
            face.embed_ms = (time.perf_counter() - t1) * 1000.0
        faces.append(face)

    logger.debug("detected %d face(s) in %.1f ms", len(faces), detect_ms)
    return faces


def face_embedding(face: DetectedFace) -> np.ndarray:
    """Return the L2-normalized embedding, computing it if absent."""
    if face.embedding is None:
        # Only reachable if detect_faces was called with embed=False.
        app = _facerec._ensure()
        face.embedding = app.get_embeddings([face.bbox])  # type: ignore[attr-defined]
    return face.embedding
