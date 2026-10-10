---
type: adr
status: proposed
date: 2026-10-10
---

# ADR-0003 Async intake and pull workers (proposed)

## Context

The counts are for the BI team, who accept day-old data. A synchronous
`/count` makes the uploader wait for the model, sizes the server for peak
load, and loses the count if the process dies. Later the counts should feed
an OLAP store in near real time, and none may ever be lost.

## Proposal

Separate accepting a photo from counting it. A small intake API stores the
photo (id = sha256 of its bytes) and a job, then replies `202`. Workers pull
jobs with an expiring lease, count, and append results keyed by
`(photo_sha, model_version)`. This works on hemin's GPU whenever hemin is up,
and as a memory-capped night window on the apps server.

Phases:

1. A job collection in a separate MongoDB database; no new infrastructure.
2. Celery with a RabbitMQ broker when volume needs it. Redis's visibility
   timeout silently re-runs long jobs.
3. Kafka (or Redpanda) with the OLAP work, for replay against new model
   versions and fan-out to several consumers.

Records are shaped as events (`photo_received`, `count_completed`) from day
one, so later phases swap the transport, not the schema.

## Open before accepting

Daily photo volume and arrival pattern; photo source and the metadata BI
needs at minimum; whether hemin may run as a scheduled worker; approvals on
the shared host. Full write-up: `docs/SERVING_STRATEGY.md`. Tracking: issue #7.

See [[Serving pipeline]], [[Demo API on the apps server]].
