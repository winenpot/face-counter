"""Read-only Label Studio status probe: projects, per-project progress, per-annotator
counts, and prediction-vs-annotation box diffs (rubber-stamp detection).

Strictly GET-only for data (the client's PAT->access token refresh is an auth call).
Writes the raw pulled data under runs/ for re-analysis without hitting the server again.
"""
import collections
import json
import sys
import time
from pathlib import Path

from face_counter.label_studio import setup_project as sp

OUT = Path(__file__).resolve().parents[1] / "runs/labeler_qc/ls_status_dump.json"


def get(ls, path, params=None):
    return ls.request("GET", path, params=params)


def all_tasks(ls, pid):
    tasks, page = [], 1
    while True:
        r = get(ls, "/api/tasks/", {"project": pid, "page": page, "page_size": 100, "fields": "all"})
        batch = r.get("tasks", r.get("results", [])) if isinstance(r, dict) else r
        total = r.get("total") if isinstance(r, dict) else None
        tasks += batch
        if not batch or total is None or len(tasks) >= total:
            break
        page += 1
    return tasks


def pull():
    token = sp.read_token(Path(sp.DEFAULT_ENV))
    with sp.ssh_tunnel(sp.DEFAULT_SSH_HOST, sp.DEFAULT_REMOTE_PORT) as base:
        ls = sp.LabelStudio(base, token)
        users = sp._results(get(ls, "/api/users/"))
        projects = sp._results(get(ls, "/api/projects/", {"page_size": 1000}))
        dump = {"pulled_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "users": users, "projects": []}
        for p in sorted(projects, key=lambda p: p["id"]):
            tasks = all_tasks(ls, p["id"])
            # make sure annotations + predictions are present for labeled tasks
            for i, t in enumerate(tasks):
                if (t.get("total_annotations", 0) or t.get("cancelled_annotations", 0)) and (
                    "annotations" not in t or "predictions" not in t
                    or len(t.get("annotations") or []) < t.get("total_annotations", 0)
                ):
                    tasks[i] = get(ls, f"/api/tasks/{t['id']}/")
            dump["projects"].append({"project": p, "tasks": tasks})
    OUT.write_text(json.dumps(dump))
    return dump


# --- analysis -----------------------------------------------------------------

def boxes(result):
    out = []
    for r in result or []:
        if r.get("type") != "rectanglelabels":
            continue
        v = r.get("value", {})
        labs = v.get("rectanglelabels") or []
        out.append((v["x"], v["y"], v["width"], v["height"], labs[0] if labs else None))
    return out


def iou(a, b):
    ax2, ay2, bx2, by2 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw = max(0.0, min(ax2, bx2) - max(a[0], b[0]))
    ih = max(0.0, min(ay2, by2) - max(a[1], b[1]))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def diff(ann, pred):
    pairs = sorted(((iou(a, p), i, j) for i, a in enumerate(ann) for j, p in enumerate(pred)), reverse=True)
    ua, up, matched = set(), set(), []
    for s, i, j in pairs:
        if s < 0.5:
            break
        if i in ua or j in up:
            continue
        ua.add(i); up.add(j); matched.append((s, i, j))
    kept = sum(1 for s, _, _ in matched if s > 0.999)
    relabeled = sum(1 for _, i, j in matched if ann[i][4] != pred[j][4])
    return {"kept": kept, "adjusted": len(matched) - kept, "deleted": len(pred) - len(matched),
                "new": len(ann) - len(matched), "relabeled": relabeled}


def fname(t):
    d = t.get("data", {})
    return d.get("file_name") or Path(str(d.get("image", ""))).name, d.get("photo_id")


def report(dump):
    users = {u["id"]: (u.get("email") or u.get("username")) for u in dump["users"]}
    print(f"pulled_at {dump['pulled_at']}   users={len(users)}")
    print()
    hdr = f"{'id':>3}  {'title':<26} {'tasks':>5} {'labeled':>7} {'drafts*':>7} {'skipped':>7} {'last_annotation':<17} {'pred/lab':>8} {'ann/lab':>8}"
    print(hdr); print("-" * len(hdr))
    per_user, flagged, stats = {}, [], {}
    for entry in dump["projects"]:
        p, tasks = entry["project"], entry["tasks"]
        pid = p["id"]
        labeled = [t for t in tasks if t.get("total_annotations", 0) > 0]
        skipped = sum(1 for t in tasks if t.get("total_annotations", 0) == 0 and t.get("cancelled_annotations", 0))
        drafts = sum(1 for t in tasks if t.get("drafts"))
        by_user, last = collections.Counter(), ""
        npred = nann = 0
        for t in labeled:
            subs = [a for a in t.get("annotations", []) if not a.get("was_cancelled")]
            preds = {pr.get("id"): pr for pr in t.get("predictions", [])}
            for a in subs:
                cb = a.get("completed_by")
                cb = cb.get("id") if isinstance(cb, dict) else cb
                by_user[users.get(cb, cb)] += 1
                last = max(last, a.get("updated_at") or a.get("created_at") or "")
            if pid == 3 or not subs:
                continue
            a = subs[-1]
            pr = preds.get(a.get("parent_prediction")) or (t["predictions"][-1] if t.get("predictions") else None)
            pb, ab = boxes(pr["result"] if pr else []), boxes(a.get("result"))
            npred += len(pb); nann += len(ab)
            d = diff(ab, pb)
            if pb and d["kept"] == len(pb) == len(ab) and d["relabeled"] == 0:
                fn, phid = fname(t)
                cb = a.get("completed_by"); cb = cb.get("id") if isinstance(cb, dict) else cb
                flagged.append((pid, p["title"], t.get("inner_id"), t["id"], fn, phid, len(pb), users.get(cb, cb),
                                (a.get("updated_at") or "")[:16], len(subs)))
            elif pb and d["kept"] == len(pb) == len(ab):
                stats.setdefault(pid, []).append((t.get("inner_id"), t["id"], "geometry untouched, only relabels", d))
        per_user[(pid, p["title"])] = by_user
        n = len(labeled)
        pl = f"{npred / n:8.1f}" if n and pid != 3 else f"{'-':>8}"
        al = f"{nann / n:8.1f}" if n and pid != 3 else f"{'-':>8}"
        print(f"{pid:>3}  {p['title'][:26]:<26} {len(tasks):>5} {n:>7} {drafts:>7} {skipped:>7} {last[:16] or '-':<17} {pl} {al}")
    print("\n* drafts: the task API only returns drafts of the token's own user.")
    print("  pred/lab, ann/lab: mean predicted / annotated boxes per labeled task (project 3 not analysed).")
    print("\nPER-ANNOTATOR SUBMITTED COUNTS")
    for (pid, title), c in per_user.items():
        if c:
            print(f"  #{pid} {title}: " + ", ".join(f"{u}={n}" for u, n in c.most_common()))
    print("\nFLAGGED (submitted annotation identical to predictions: every box kept IoU>0.999, none added/deleted/relabeled)")
    if not flagged:
        print("  none")
    for f in flagged:
        print(f"  project #{f[0]} {f[1]}: inner_id #{f[2]} -> id {f[3]} -> {f[4]} (photo_id {f[5]}), "
              f"{f[6]} boxes, by {f[7]} at {f[8]}, submissions={f[9]}")
    for pid, rows in stats.items():
        for r in rows:
            print(f"  note project #{pid}: inner_id #{r[0]} -> id {r[1]}: {r[2]} {r[3]}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--offline":
        report(json.loads(OUT.read_text()))
    else:
        report(pull())
