"""Read a Label Studio JSON export into per-photo boxes in displayed pixels.

Boxes are stored as percentages of the image as the browser shows it, i.e.
after EXIF rotation, which is also what the detectors see (they load through
`ImageOps.exif_transpose`). So percent -> pixels uses the annotation's own
`original_width/height`, and detections compare directly.

Per photo, the latest submitted (not cancelled) annotation is used; drafts
never count. Anything that looks unfinished is kept as a warning on the
photo rather than silently fixed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from face_counter.utils.taxonomy import PRODUCT

UNTAGGED = "untagged"


@dataclass(frozen=True)
class Box:
    xyxy: tuple[float, float, float, float]
    label: str


@dataclass
class Photo:
    task_id: int  # Label Studio's global id (URL ?task=<id>, API)
    inner_id: int  # the per-project "#N" a labeler sees
    photo_id: str
    file_name: str
    width: int
    height: int
    scene: str
    capture: list[str]
    photo_issue: list[str]
    boxes: list[Box]
    warnings: list[str] = field(default_factory=list)


def _choices(result: list[dict], name: str) -> list[str]:
    return [
        c
        for r in result
        if r.get("type") == "choices" and r.get("from_name") == name
        for c in r["value"].get("choices", [])
    ]


def parse_task(task: dict) -> Photo | None:
    """One task -> Photo, or None when nothing was submitted."""
    submitted = [a for a in task.get("annotations", []) if not a.get("was_cancelled")]
    if not submitted:
        return None
    ann = max(submitted, key=lambda a: a.get("updated_at") or a.get("created_at") or "")
    warnings = []
    if len(submitted) > 1:
        warnings.append(
            f"{len(submitted)} submitted annotations; using the latest (id {ann['id']})"
        )
    for d in task.get("drafts") or []:
        if (d.get("updated_at") or "") > (ann.get("updated_at") or ""):
            warnings.append("a draft is newer than the submission (unsaved changes)")
            break

    data = task["data"]
    boxes, size = [], None
    for r in ann["result"]:
        v = r.get("value", {})
        if r.get("type") != "rectanglelabels" or "x" not in v:
            continue
        if v.get("rotation", 0):
            raise ValueError(
                f"task {task['id']} ({data.get('file_name')}): rotated box; "
                "rotated rectangles are not supported"
            )
        W, H = r["original_width"], r["original_height"]
        size = size or (W, H)
        if (W, H) != size:
            raise ValueError(f"task {task['id']}: boxes disagree on the image size")
        x1, y1 = v["x"] * W / 100, v["y"] * H / 100
        x2, y2 = x1 + v["width"] * W / 100, y1 + v["height"] * H / 100
        # No label at all counts as `product` (decided 2026-09-29).
        label = next(iter(v.get("rectanglelabels") or []), "") or PRODUCT
        boxes.append(Box((x1, y1, x2, y2), label))

    scene = _choices(ann["result"], "scene")
    w, h = size or (0, 0)
    return Photo(
        task_id=task["id"],
        inner_id=task.get("inner_id", 0),
        photo_id=data.get("photo_id", ""),
        file_name=data.get("file_name", ""),
        width=w,
        height=h,
        scene=scene[0] if scene else UNTAGGED,
        capture=_choices(ann["result"], "capture"),
        photo_issue=_choices(ann["result"], "photo_issue"),
        boxes=boxes,
        warnings=warnings,
    )


def load(path: str | Path) -> list[Photo]:
    """Every photo with a submitted annotation, in export order."""
    tasks = json.loads(Path(path).read_text(encoding="utf-8"))
    return [p for p in map(parse_task, tasks) if p is not None]
