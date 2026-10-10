---
type: adr
status: accepted
date: 2026-10-10
---

# ADR-0002 Pack-type stage off by default

## Context

The canned/glass stage is zero-shot CLIP ViT-L/14. On CPU it costs ~15 s of
forward pass per 44-crop photo, plus a 4.4 s reload on every call, and keeps
a ~2 GB resident floor. The deployment host is shared with production
services. Its headline accuracy (93.8%) was measured on human-drawn boxes,
from a set with 26 rival cans, against an 82% majority-class floor; it has
never been measured on detector boxes.

## Decision

`ServeConfig.classify` defaults to False (env `FACE_COUNTER_CLASSIFY`). By
default the demo returns detected units and neutral boxes only. The stage
comes back after a cheaper classifier wins on detector boxes
(`docs/PACK_TYPE_ALTERNATIVES.md`).

## Consequences

- Per photo: 24.6 s → ~0.73 s on hemin, ~5 s on the apps server. No torch in
  the process.
- The demo shows counts, not a canned/glass split. The response says so in a
  caveat, and `/health` reports `pack_classifier: null`.
- The experimental `debug=true` path still loads CLIP; it is opt-in and caveated.
- Box shape alone is not a replacement: 86.2% on rival detector boxes against
  an 81.9% floor (see [[2026-10-10 Serving investigation]]).

Tracking: issues #2 (measure CLIP on detector boxes) and #3 (cost; alternatives).
