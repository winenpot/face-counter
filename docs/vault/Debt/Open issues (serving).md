---
type: debt
updated: 2026-10-10
---

# Open issues (serving)

GitHub issues on `winenpot/face-counter` that came out of the serving work.
The repo is public, so issues carry no credentials or IP addresses.

| # | State | What | Why it matters |
|---|---|---|---|
| 2 | open | Pack-type accuracy measured on human boxes, from a small, imbalanced gold set | The 93.8% may not hold on detector boxes; the box-shape baseline lost ~7 points making that move |
| 3 | open | CLIP stage too heavy for CPU; reloaded on every call | 15 s + 4.4 s per photo, ~2 GB; blocks turning the stage back on |
| 4 | **closed, filed in error** | "ultralytics in dev group" | False: a misread of concatenated `sed` output. Kept here so nobody re-files it |
| 5 | open | Dependency and model delivery blocked by network paths; hemin's venv hand-patched | hemin's venv cannot be rebuilt from `uv.lock` alone; HF Hub reachability |
| 6 | open | Demo API: blockers before wider exposure | key rotated, loopback bind (done); left: TLS front door, memory headroom (978/1200 MiB), compose file |
| 7 | open | Counts not persisted, no store/time metadata | BI cannot use the output yet; see [[ADR-0003 Async intake and pull workers (proposed)]] |

Also open, older: #1 (shelf slots with no identifiable product; blocks gold
labeling rules).

Smaller known defects without their own issue are in [[Serving pipeline]]
("Known defects").
