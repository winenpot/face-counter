---
type: devops
---

# Demo API on the apps server

The detection-only demo, deployed 2026-10-10 at the user's instruction. It
runs on the apps server (ssh alias `atpg`) rather than the db server named in
the demo plan's T7: there is no SSH access to the db server. Measurements are
in [[2026-10-10 Serving investigation]]; open blockers in issue #6.

## What is running

| | |
|---|---|
| Container | `face-counter-serve`, image `face-counter-serve:ebbb6fe` (961 MB, no torch/transformers/ultralytics inside) |
| Built from | `deploy/serve.Dockerfile`, in a shallow clone of the public repo at `~/code/face-counter` on the server |
| Model | `~/code/face-counter/models/yolo26l-sku110k.onnx`, mounted read-only at `/app/models`; sha256 `3e1ee017…`, identical on hemin, laptop and server |
| Bind | app listens on 0.0.0.0:8000 inside the container; host publishes **127.0.0.1:8096** only. Not reachable from the internet (verified from outside) |
| Limits | `--memory 1200m --memory-swap 1200m --cpus 2 --cpu-shares 256 --pids-limit 256`, `FACE_COUNTER_ORT_THREADS=2` |
| Hardening | `--read-only --tmpfs /tmp:size=64m --cap-drop ALL --security-opt no-new-privileges`, runs as uid 65534 |
| Lifecycle | `--restart unless-stopped`, Docker healthcheck on `/health`, logs capped at 3 × 10 MB |
| API key | random, rotated 2026-10-10, in `~/code/face-counter/.serve.env` on the server (mode 600, git-excluded), passed with `--env-file`. Read it there; never paste it into git, issues or chat |

The cap is the point of the design. If the process outgrows 1200 MiB, the
kernel kills this container, not the production database next to it.

## How to look at it

Open a tunnel from the laptop, then browse locally:

    ssh -N -L 8096:127.0.0.1:8096 atpg
    # http://localhost:8096/docs (Swagger UI; put the key in the x-api-key field)

To see the key: `ssh atpg cat ~/code/face-counter/.serve.env`. Never paste it
into git, issues or chat.

## Binding rule

The app listens on `0.0.0.0` *inside* the container. The host publishes it on
`127.0.0.1` only. The internet should reach apps only through a TLS reverse
proxy, and atpg has none yet. Docker bypasses ufw, so the `-p` address is the
real firewall.

Cross-project standard, with the atpg audit and migration plan:
`~/Hermes-Vault/Infrastructure/Server exposure rule (bind 127.0.0.1, one front door).md`
(the user's local vault, not in this repo).

History: the container was published on all interfaces for a few hours on
2026-10-10, then moved back to loopback once the rule was adopted. The key
rotated then remains in use.

## Rebuild after a code change

    ssh atpg
    cd ~/code/face-counter && git pull --ff-only
    V=$(git rev-parse --short HEAD)
    docker build -f deploy/serve.Dockerfile --build-arg VERSION=$V -t face-counter-serve:$V .
    docker rm -f face-counter-serve
    # then re-run the docker run command below with the new tag

The full `docker run`, as used:

    docker run -d --name face-counter-serve --restart unless-stopped \
      --memory 1200m --memory-swap 1200m --cpus 2 --cpu-shares 256 --pids-limit 256 \
      --read-only --tmpfs /tmp:size=64m --cap-drop ALL --security-opt no-new-privileges \
      --log-opt max-size=10m --log-opt max-file=3 \
      -e FACE_COUNTER_ORT_THREADS=2 --env-file .serve.env \
      -v "$HOME/code/face-counter/models:/app/models:ro" \
      -p 127.0.0.1:8096:8000 \
      face-counter-serve:$V

**Debt:** these flags live only in this note. The Label Studio pattern keeps
a compose file in `deploy/` as the single source of truth, plus a deploy
script. The same is owed here as `deploy/serving/` (issue #6, T7).

## Remove

    docker rm -f face-counter-serve            # the container
    docker image rm face-counter-serve:ebbb6fe # optional: the image

Nothing else on the server was touched: no other container, network, volume
or database.

## Before anyone else uses it

Issue #6 and #8. Done: key rotated into a secret file; loopback-only bind. Left: a TLS reverse proxy as the public front door (shared atpg decision); measure a worst-case upload against the cap; move the flags into compose.
