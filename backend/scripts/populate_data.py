"""One-time dev helper: copy images/+info/ into data/ as PNG + JSON.

Converts every source photo to PNG (normalizing .jfif/.avif/etc.) and pairs it
with its metadata JSON, so `data/{person_id}.png` + `data/{person_id}.json`
matches what the repository expects.

Usage:  python scripts/populate_data.py [--source images] [--meta info]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app import config  # noqa: E402

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".jfif", ".webp", ".bmp", ".avif"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(REPO_ROOT.parent / "images"))
    parser.add_argument("--meta", default=str(REPO_ROOT.parent / "info"))
    args = parser.parse_args()

    source = Path(args.source)
    meta_dir = Path(args.meta)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    copied = skipped = 0
    for img_path in sorted(source.iterdir()):
        if img_path.suffix.lower() not in IMAGE_EXTS:
            continue
        person_id = img_path.stem.lower()

        frame = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if frame is None:
            print(f"SKIP  {img_path.name}: cannot decode")
            skipped += 1
            continue
        out_png = config.DATA_DIR / f"{person_id}.png"
        ok = cv2.imwrite(str(out_png), frame)
        if not ok:
            print(f"SKIP  {img_path.name}: PNG encode failed")
            skipped += 1
            continue

        meta_file = meta_dir / f"{person_id}.json"
        if meta_file.exists():
            info = json.loads(meta_file.read_text(encoding="utf-8"))
        else:
            info = {"name": person_id, "nid": "", "age": 0, "address": "", "number": ""}
        (config.DATA_DIR / f"{person_id}.json").write_text(
            json.dumps(info, indent=2), encoding="utf-8"
        )
        print(f"COPY  {img_path.name} -> {person_id}.png (+json)")
        copied += 1

    print(f"\nDone: {copied} copied, {skipped} skipped.")


if __name__ == "__main__":
    main()
