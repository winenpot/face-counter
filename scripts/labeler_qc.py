"""Read-only per-labeler QC for pilot batches (projects 6-10) vs gold (5). GET only."""
import csv
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

from face_counter.label_studio import setup_project as sp

PIDS = [5, 6, 7, 8, 9, 10]
ROOT = Path(__file__).resolve().parents[1]
OUTD = ROOT / "runs/labeler_qc" / datetime.now().astimezone().date().isoformat()
DUMP = ROOT / "runs/labeler_qc/labeler_qc_dump.json"


def get(ls, path, params=None):
    return ls.request("GET", path, params=params)


def pull():
    token = sp.read_token(Path(sp.DEFAULT_ENV))
    with sp.ssh_tunnel(sp.DEFAULT_SSH_HOST, sp.DEFAULT_REMOTE_PORT) as base:
        ls = sp.LabelStudio(base, token)
        users = sp._results(get(ls, "/api/users/"))
        projects = {p["id"]: p for p in sp._results(get(ls, "/api/projects/", {"page_size": 1000}))}
        dump = {"pulled_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "users": users, "projects": []}
        for pid in PIDS:
            tasks, page = [], 1
            while True:
                r = get(ls, "/api/tasks/", {"project": pid, "page": page, "page_size": 100})
                b = r.get("tasks", []); tasks += b
                if not b or len(tasks) >= r.get("total", 0):
                    break
                page += 1
            full = [get(ls, f"/api/tasks/{t['id']}/") if (t.get("total_annotations") or t.get("cancelled_annotations")) else t
                    for t in tasks]
            p = projects.get(pid, {"id": pid, "title": str(pid)})
            dump["projects"].append({"project": {"id": pid, "title": p.get("title")}, "tasks": full})
    DUMP.write_text(json.dumps(dump))
    return dump


def boxes(result):
    out = []
    for r in result or []:
        if r.get("type") != "rectanglelabels":
            continue
        v = r["value"]; labs = v.get("rectanglelabels") or []
        out.append((v["x"], v["y"], v["width"], v["height"], labs[0] if labs else ""))
    return out


def iou(a, b):
    iw = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    ih = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    i = iw * ih; u = a[2] * a[3] + b[2] * b[3] - i
    return i / u if u > 0 else 0.0


def diff(ann, pred):
    pairs = sorted(((iou(a, p), i, j) for i, a in enumerate(ann) for j, p in enumerate(pred)), reverse=True)
    ua, up, m = set(), set(), []
    for s, i, j in pairs:
        if s < 0.5: break
        if i in ua or j in up: continue
        ua.add(i); up.add(j); m.append(s)
    kept = sum(s > 0.999 for s in m)
    named = sum(1 for b in ann if b[4] not in ("product", ""))
    return {"predicted": len(pred), "annotated": len(ann), "kept": kept, "adjusted": len(m) - kept,
                "deleted": len(pred) - len(m), "new": len(ann) - len(m), "named": named}


def analyse(dump):
    users = {u["id"]: (u.get("email") or u.get("username")) for u in dump["users"]}
    rows, multi = [], []
    for e in dump["projects"]:
        pid, title = e["project"]["id"], e["project"]["title"]
        for t in e["tasks"]:
            subs = [a for a in t.get("annotations") or [] if not a.get("was_cancelled")]
            if len(subs) > 1:
                multi.append((pid, t.get("inner_id"), t["id"], t["data"].get("photo_id"),
                              ";".join(users.get(a["completed_by"] if not isinstance(a["completed_by"], dict) else a["completed_by"]["id"], "?") for a in subs)))
            preds = {p["id"]: p for p in t.get("predictions") or []}
            for a in subs:
                cb = a["completed_by"]; cb = cb["id"] if isinstance(cb, dict) else cb
                pr = preds.get(a.get("parent_prediction")) or ((t.get("predictions") or [None])[-1])
                d = diff(boxes(a.get("result")), boxes(pr["result"] if pr else []))
                ed = d["adjusted"] + d["deleted"] + d["new"] + d["named"]
                rows.append(dict(project=pid, title=title, inner_id=t.get("inner_id"), task_id=t["id"],
                                 photo_id=t["data"].get("photo_id"), annotation_id=a["id"], labeler=users.get(cb, cb),
                                 **d, edits=ed, edit_rate=(ed / d["predicted"]) if d["predicted"] else None,
                                 deleted_pct=(d["deleted"] / d["predicted"]) if d["predicted"] else None,
                                 lead_time=a.get("lead_time"), n_submissions=len(subs),
                                 created_at=a.get("created_at"), updated_at=a.get("updated_at")))
    return rows, multi


def fmt(x, p="{:.1%}"):
    return "-" if x is None else p.format(x)


def report(dump):
    rows, multi = analyse(dump)
    OUTD.mkdir(parents=True, exist_ok=True)
    with open(OUTD / "per_task.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    L = [f"Labeler QC (read-only)  pulled_at {dump['pulled_at']}",
         "Projects: " + ", ".join(f"#{e['project']['id']} {e['project']['title']} ({len(e['tasks'])} tasks)" for e in dump["projects"]), ""]

    def summarise(rs):
        er = [r["edit_rate"] for r in rs if r["edit_rate"] is not None]
        dp = [r["deleted_pct"] for r in rs if r["deleted_pct"] is not None]
        lt = [r["lead_time"] for r in rs if r["lead_time"]]
        q = statistics.quantiles(er, n=4) if len(er) >= 2 else [None] * 3
        return {"n": len(rs), "er": statistics.mean(er) if er else None, "er_med": statistics.median(er) if er else None,
                    "q1": q[0], "q3": q[2], "dp": statistics.mean(dp) if dp else None,
                    "new": statistics.mean(r["new"] for r in rs), "named": statistics.mean(r["named"] for r in rs),
                    "pred": statistics.mean(r["predicted"] for r in rs),
                    "zero": sum(r["edits"] == 0 for r in rs), "lt5": sum(r["edit_rate"] is not None and r["edit_rate"] < 0.05 for r in rs),
                    "lt": statistics.median(lt) if lt else None}

    hdr = f"{'group':<38} {'photos':>6} {'pred/ph':>7} {'meanER':>7} {'medER':>6} {'IQR ER':>13} {'del%':>6} {'new/ph':>6} {'named/ph':>8} {'zero':>4} {'<5%':>4} {'med s':>6}"
    def line(name, s):
        return (f"{name[:38]:<38} {s['n']:>6} {s['pred']:>7.1f} {fmt(s['er']):>7} {fmt(s['er_med']):>6} "
                f"{fmt(s['q1'], '{:.0%}') + '-' + fmt(s['q3'], '{:.0%}'):>13} {fmt(s['dp']):>6} {s['new']:>6.2f} {s['named']:>8.2f} "
                f"{s['zero']:>4} {s['lt5']:>4} {fmt(s['lt'], '{:.0f}'):>6}")
    gold = [r for r in rows if r["project"] == 5]
    pilot = [r for r in rows if r["project"] != 5]
    L += ["REFERENCE: gold project #5 (per labeler)", hdr, "-" * len(hdr)]
    for u in sorted({r["labeler"] for r in gold}):
        L.append(line(str(u), summarise([r for r in gold if r["labeler"] == u])))
    L += ["", "PILOT BATCHES #6-10, per labeler (all batches pooled)", hdr, "-" * len(hdr)]
    for u in sorted({r["labeler"] for r in pilot}, key=str):
        L.append(line(str(u), summarise([r for r in pilot if r["labeler"] == u])))
    L += ["", "PILOT, per labeler x project", hdr, "-" * len(hdr)]
    for (u, p) in sorted({(str(r["labeler"]), r["project"]) for r in pilot}):
        L.append(line(f"{u} #{p}", summarise([r for r in pilot if str(r["labeler"]) == u and r["project"] == p])))
    L += ["", "ZERO-EDIT annotations (every predicted box kept IoU>0.999, none added/deleted/adjusted/named) - project, inner_id, global id, photo_id, labeler"]
    z = [r for r in rows if r["edits"] == 0]
    L += [f"  #{r['project']}  inner {r['inner_id']}  id {r['task_id']}  photo {r['photo_id']}  {r['labeler']}  ({r['predicted']} boxes)" for r in z] or ["  none"]
    L += ["", "MULTI-ANNOTATION tasks (>1 submitted annotation) - project, inner_id, global id, photo_id, labelers"]
    L += [f"  #{m[0]}  inner {m[1]}  id {m[2]}  photo {m[3]}  {m[4]}" for m in multi] or ["  none"]
    L += ["", "Definitions: ER (edit rate) = (adjusted+deleted+new+named)/predicted, per photo; greedy one-to-one IoU>=0.5 match vs the",
          "annotation's parent prediction (else the task's last prediction). kept = matched IoU>0.999. named = boxes whose label is not",
          "'product'/empty. zero = photos with 0 edits; <5% = photos with ER<5%. med s = median lead_time seconds (as recorded by LS).",
          "Every submitted annotation counts as one photo row (multi-annotation tasks contribute one row per annotation).",
          "CAVEAT: edit rate is a proxy for effort, not correctness. A low rate can be a correct acceptance of good predictions",
          "(easy photo) and a high rate can be wrong edits. Zero-edit photos are the ones to open by eye first. lead_time includes idle time."]
    txt = "\n".join(L)
    (OUTD / "report.txt").write_text(txt + "\n")
    print(txt)


if __name__ == "__main__":
    report(json.loads(DUMP.read_text()) if "--offline" in sys.argv else pull())
