"""Assign every photo to train / val / test BY STORE, and pick the photos to label first.

Why by store: photos from the same store (same shelf, same visit) are near-duplicates.
If one lands in training and its twin in test, the accuracy numbers lie.

Assignment is a stable hash of store_id, so re-running after new exports never moves
an existing store to another split: the test set stays fixed forever.

Labeling batches are numbered and cumulative: each run only pulls NEW train photos
that have never appeared in any previous label_batch_*.txt. A photo already sent to
labelers can never be re-picked into a later batch -- re-sending the same work is the
one mistake this can't silently make, even if you re-run with different flags.

Outputs (data/splits/):
    splits.csv           photo_id, file_name, store_id, split
    test_labeling.txt    the ~30 test photos to label first (never overwritten without --force)
    label_batch_01.txt   ~250 diverse train photos for the first labeling round
    label_batch_02.txt   the next ~250 NEW train photos (created on the next run, only if any exist)

Usage:
    uv run shelf-splits
    uv run shelf-splits --test-pct 10 --val-pct 10 --test-size 30 --batch-size 250
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import random
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

from face_counter.config import DEFAULT_MANIFEST, DEFAULT_SPLITS_DIR

log = logging.getLogger("splits")
SALT = "shelf-detector-v1"  # never change: it would reshuffle which stores are in test
BATCH_PATTERN = re.compile(r"^label_batch_(\d+)\.txt$")


def group_key(row) -> str:
    """Store is the leakage unit. Fall back to visit, then the photo itself.

    store_id here must already be the durable store identity (atpg's
    store_join resolves photos.files.store_code -- a per-visit registration
    code -- through location.code -> permanent_id). Grouping on the raw
    per-visit code instead would split by visit, not by store, and defeat
    this guard entirely: docs/PHASE0_REMAINING.md §1.
    """
    for col in ("store_id", "visit_id"):
        val = row.get(col)
        if isinstance(val, str) and val.strip() and val.lower() != "nan":
            return f"{col}:{val.strip()}"
    return f"photo:{row['photo_id']}"


def split_for(key: str, test_pct: int, val_pct: int) -> str:
    bucket = int(hashlib.sha256(f"{SALT}:{key}".encode()).hexdigest(), 16) % 100
    if bucket < test_pct:
        return "test"
    if bucket < test_pct + val_pct:
        return "val"
    return "train"


def diverse_sample(df: pd.DataFrame, n: int, seed: int, max_per_group: int | None = None) -> list[str]:
    """Round-robin across cities, then stores, so the sample covers as many places as possible."""
    rng = random.Random(seed)
    by_group: dict[str, list[str]] = defaultdict(list)
    for _, r in df.iterrows():
        by_group[r["group"]].append(r["photo_id"])
    for ids in by_group.values():
        rng.shuffle(ids)
    city_of = df.groupby("group")["city"].first().to_dict()
    groups = list(by_group)
    rng.shuffle(groups)
    # interleave cities: take one store from each city in turn
    by_city: dict[str, list[str]] = defaultdict(list)
    for g in groups:
        by_city[str(city_of.get(g, ""))].append(g)
    ordered: list[str] = []
    city_lists = list(by_city.values())
    rng.shuffle(city_lists)
    while any(city_lists):
        for lst in city_lists:
            if lst:
                ordered.append(lst.pop(0))

    picked: list[str] = []
    rnd = 0
    while len(picked) < n:
        progressed = False
        for g in ordered:
            if max_per_group is not None and rnd >= max_per_group:
                break
            if rnd < len(by_group[g]):
                picked.append(by_group[g][rnd])
                progressed = True
                if len(picked) >= n:
                    break
        if not progressed:
            break
        rnd += 1
    return picked


def make_splits(manifest: Path, out_dir: Path, test_pct: int, val_pct: int,
                test_size: int, batch_size: int, seed: int, force: bool) -> pd.DataFrame:
    df = pd.read_csv(manifest, dtype=str).fillna("")
    before = len(df)
    df = df.drop_duplicates(subset="sha256", keep="first")  # exact duplicate uploads
    if len(df) < before:
        log.info("dropped %d exact duplicate photos", before - len(df))

    df["group"] = df.apply(group_key, axis=1)
    n_fallback = df["group"].str.startswith("photo:").sum()
    if n_fallback:
        log.warning("%d photos have no store_id/visit_id; they are split individually "
                    "(leakage risk). Check the field mapping in configs/export.yaml.", n_fallback)
    df["split"] = df["group"].map(lambda k: split_for(k, test_pct, val_pct))

    # Leakage guard: a store must never appear in two splits.
    per_group = df.groupby("group")["split"].nunique()
    assert (per_group == 1).all(), "a store appears in more than one split"

    out_dir.mkdir(parents=True, exist_ok=True)
    df[["photo_id", "file_name", "store_id", "split"]].to_csv(out_dir / "splits.csv", index=False)

    test_file = out_dir / "test_labeling.txt"
    if test_file.exists() and not force:
        log.info("%s exists; keeping the fixed test set (use --force to regenerate)", test_file)
    else:
        test_ids = diverse_sample(df[df.split == "test"], test_size, seed, max_per_group=2)
        _write_list(test_file, df, test_ids)

    _write_next_batch(df, out_dir, batch_size, seed)

    summary = df.groupby("split").agg(photos=("photo_id", "count"), stores=("group", "nunique"))
    log.info("split summary:\n%s", summary.to_string())
    if (df.split == "test").sum() < test_size:
        log.warning("only %d test photos available; raise --test-pct", (df.split == "test").sum())
    return df


def _already_sent(out_dir: Path) -> set[str]:
    """File names that appear in any existing label_batch_*.txt.

    Scanning every prior batch (not just the last one) means a photo can
    never come back in a later batch even if an old batch file gets edited,
    reordered, or a batch number is skipped -- the guarantee holds no matter
    what state data/splits/ is in.
    """
    sent: set[str] = set()
    for f in out_dir.glob("label_batch_*.txt"):
        if BATCH_PATTERN.match(f.name):
            sent.update(f.read_text(encoding="utf-8").split())
    return sent


def _write_next_batch(df: pd.DataFrame, out_dir: Path, batch_size: int, seed: int) -> None:
    """Pick the next numbered label_batch_NN.txt from train photos never sent before.

    Never overwrites an existing batch file, and never re-picks a photo that
    already appears in any prior batch -- the two things that would let the
    same photo reach a labeler twice. If nothing new is available, no file
    is written at all rather than writing an empty or duplicate batch.
    """
    existing = sorted(
        int(m.group(1))
        for f in out_dir.glob("label_batch_*.txt")
        if (m := BATCH_PATTERN.match(f.name))
    )
    next_n = (existing[-1] + 1) if existing else 1

    sent = _already_sent(out_dir)
    pool = df[(df.split == "train") & (~df.file_name.isin(sent))]
    if pool.empty:
        log.info(
            "no new train photos to batch (%d already sent across %d batch file(s))",
            len(sent), len(existing),
        )
        return

    batch_ids = diverse_sample(pool, batch_size, seed, max_per_group=3)
    _write_list(out_dir / f"label_batch_{next_n:02d}.txt", df, batch_ids)


def _write_list(path: Path, df: pd.DataFrame, ids: list[str]) -> None:
    names = df.set_index("photo_id").loc[ids, "file_name"].tolist()
    path.write_text("\n".join(names) + ("\n" if names else ""), encoding="utf-8")
    log.info("wrote %d photos -> %s", len(names), path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--out-dir", default=str(DEFAULT_SPLITS_DIR))
    ap.add_argument("--test-pct", type=int, default=10, help="%% of stores held out for test")
    ap.add_argument("--val-pct", type=int, default=10, help="%% of stores held out for validation")
    ap.add_argument("--test-size", type=int, default=30, help="test photos to label first")
    ap.add_argument("--batch-size", type=int, default=250, help="train photos in labeling batch 01")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--force", action="store_true", help="regenerate test_labeling.txt")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    make_splits(Path(args.manifest), Path(args.out_dir), args.test_pct, args.val_pct,
                args.test_size, args.batch_size, args.seed, args.force)


if __name__ == "__main__":
    main()
