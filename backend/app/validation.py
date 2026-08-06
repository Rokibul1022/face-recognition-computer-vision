"""Upload validation.

We do NOT gate purely on file extension: extensions are unreliable (`.jfif`
is just JPEG bytes under another name, and a mislabeled file should be
rejected safely rather than crashing the pipeline). Instead we sniff the actual
bytes with PIL before handing them to the detector.
"""
from __future__ import annotations

import io
import logging

from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)

# Accepted image extensions — advisory only; content sniffing is authoritative.
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".jfif", ".webp", ".bmp"}

_EXT_TO_FORMAT = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".jfif": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
    ".bmp": "BMP",
}


def sniff_image(upload: UploadFile) -> tuple[bytes, str]:
    """Read an upload, verify it decodes as an allowed image, return bytes + format."""
    filename = (upload.filename or "").lower()
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[1]

    if ext not in ALLOWED_IMAGE_EXTS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported image type '{ext or 'unknown'}'. Allowed: "
            + ", ".join(sorted(ALLOWED_IMAGE_EXTS)),
        )

    data = upload.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload.")

    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as img:
            # .verify() decodes the image header and scan lines without keeping
            # pixel data — cheap and catches truncated/corrupt uploads.
            img.verify()
    except Exception:
        logger.warning("Rejected upload %s: content sniffing failed.", filename)
        raise HTTPException(
            status_code=400,
            detail="File contents do not match an image and were rejected.",
        )

    return data, _EXT_TO_FORMAT.get(ext, "PNG")
