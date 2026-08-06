"""Rebuild the FAISS gallery index from the data/ folder.

Usage:  python scripts/build_gallery.py
Runs the detector over every enrollment photo, averages embeddings per person,
and writes gallery.index + gallery_meta.json.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.matcher import GalleryMatcher  # noqa: E402
from app.repository import PersonRepository  # noqa: E402


def main() -> None:
    t0 = time.perf_counter()
    repo = PersonRepository()
    matcher = GalleryMatcher()
    n = matcher.build_from_repo(repo, force=True)
    elapsed = time.perf_counter() - t0
    print(f"Enrolled {n} person(s) in {elapsed:.1f}s.")
    print(f"Index:  {matcher.index_path}")
    print(f"Meta:   {matcher.meta_path}")


if __name__ == "__main__":
    main()
