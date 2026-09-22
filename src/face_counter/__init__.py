"""Shelf Detector: count product faces on retail shelf photos.

Phase 0 (foundations) lives here: exporting photos from MongoDB, fixing a
leakage-free test set, and preparing Label Studio. See docs/ROADMAP.md.
"""


def main() -> None:
    print(
        "face-counter — Phase 0 tooling.\n"
        "  shelf-export      export photos + manifest from MongoDB\n"
        "  shelf-splits      assign train/val/test by store\n"
        "  shelf-label-prep  build Label Studio config + tasks\n"
        "See README.md and docs/ROADMAP.md."
    )
