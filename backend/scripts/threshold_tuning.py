"""Threshold tuning pass.

Builds the gallery, then reports cosine-similarity scores for same-person and
different-person pairs drawn from data/ so you can pick a production threshold.

Usage:  python scripts/threshold_tuning.py
"""
from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.matcher import GalleryMatcher  # noqa: E402
from app.repository import PersonRepository  # noqa: E402


def main() -> None:
    repo = PersonRepository()
    matcher = GalleryMatcher()
    matcher.ensure(repo)

    ids = matcher.ids
    if len(ids) < 2:
        print("Need at least 2 enrolled people for tuning.")
        return

    # Per-person per-photo embeddings (not averaged) so we test recognition
    # from a *single* photo against the averaged gallery vectors.
    raw: dict[str, list[np.ndarray]] = {}
    for pid in ids:
        for path in repo.photo_paths(pid):
            raw.setdefault(pid, []).extend(repo._embeddings_from_file(path))

    same, diff = [], []
    for pid, embs in raw.items():
        for emb in embs:
            if not matcher.is_ready():
                continue
            best, score = matcher.search(emb)
            bucket = same if best == pid else diff
            bucket.append(score)

    def summarize(name: str, scores: list[float]) -> None:
        if not scores:
            print(f"{name:12s} no samples")
            return
        arr = np.array(scores)
        print(
            f"{name:12s} n={len(arr):3d}  min={arr.min():.3f}  "
            f"p25={np.percentile(arr,25):.3f}  med={np.median(arr):.3f}  "
            f"p75={np.percentile(arr,75):.3f}  max={arr.max():.3f}"
        )

    print("\nSame-person similarity (should be high):")
    summarize("same", same)
    print("Different-person similarity (should be low):")
    summarize("different", diff)

    # Suggest operating points.
    if same and diff:
        lo = min(diff)
        hi = max(diff)
        if hi <= lo:
            print("\nRanges do not overlap — any threshold in (max_diff, min_same] works.")
        else:
            print(
                "\nRanges overlap: there is no threshold that separates them "
                "perfectly. Prefer a value closer to max(diff) to kill false "
                "positives; accept some false negatives."
            )

    print(f"\nCurrent configured threshold: {float(sys.argv[1]) if len(sys.argv) > 1 else 'see app/config.py'}")


if __name__ == "__main__":
    main()
