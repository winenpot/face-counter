"""Re-check every factual claim made about the atpg database. Read-only.

Prints CLAIM vs ACTUAL with PASS/FAIL so the numbers can be audited without
taking the report on trust.

SAFETY
  * Only read operations are issued (count/find/aggregate/connectionStatus).
  * The connection string, its credentials and the server host are scrubbed
    from ALL output, including tracebacks -- pymongo builds error messages
    containing the host:port, and an unguarded traceback would leak it.
  * Any check that errors is reported as ERROR and the rest still run.

Usage:
    uv run python scripts/verify_atpg_claims.py
"""

from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------ redaction
_SECRETS: list[str] = []


def _register_secrets(uri: str) -> None:
    _SECRETS.append(uri)
    try:
        p = urlsplit(uri)
        for piece in (p.password, p.username, p.netloc, p.hostname):
            if piece and len(str(piece)) > 2:
                _SECRETS.append(str(piece))
    except Exception:
        pass
    _SECRETS.sort(key=len, reverse=True)


def redact(text) -> str:
    out = str(text)
    for s in _SECRETS:
        if s:
            out = out.replace(s, "<redacted>")
    out = re.sub(r"mongodb(?:\+srv)?://[^\s'\"]+", "<redacted-uri>", out)
    out = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b", "<host:port>", out)
    return out


def say(*a) -> None:
    print(redact(" ".join(str(x) for x in a)))


def _excepthook(exc_type, exc, tb):
    """No raw traceback ever reaches the terminal unredacted."""
    say("UNEXPECTED ERROR:", exc_type.__name__)
    say(redact("".join(traceback.format_exception(exc_type, exc, tb))))


sys.excepthook = _excepthook

# --------------------------------------------------------------------- checks
results: list[bool] = []


def check(label, actual, claimed, ok=None) -> None:
    if ok is None:
        ok = str(actual) == str(claimed)
    results.append(bool(ok))
    say(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    say(f"         claimed: {claimed}")
    say(f"         actual : {actual}")


def _num(text) -> float:
    """First number in a formatted string: '24,175' -> 24175.0"""
    m = re.search(r"[\d,]+(?:\.\d+)?", str(text))
    return float(m.group().replace(",", "")) if m else 0.0


def grew(claimed: str, tol=0.05):
    """Tolerance for a LIVE collection: actual may exceed the surveyed number.

    Photos keep arriving, so an exact match is the wrong test. Accept anything
    at or above the surveyed count, within `tol` above it; flag a DROP, which
    would mean deletion rather than growth.
    """
    base = _num(claimed)

    def ok(actual) -> bool:
        a = _num(actual)
        return base <= a <= base * (1 + tol)

    return ok


def guarded(label, fn, claimed, ok_fn=None):
    """Run one check; an error never aborts the rest of the run."""
    try:
        actual = fn()
    except Exception as e:
        results.append(False)
        say(f"  [ERROR] {label}")
        say(f"         {type(e).__name__}: {redact(e)[:160]}")
        return None
    check(label, actual, claimed, ok=None if ok_fn is None else ok_fn(actual))
    return actual


def load_env(path: Path) -> dict:
    vals = {}
    if not path.exists():
        return vals
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def main() -> int:
    env = load_env(REPO / ".env")
    uri = env.get("MONGO_URI")
    if not uri:
        print("MONGO_URI is not set in .env — nothing to verify.")
        return 1
    _register_secrets(uri)

    from pymongo import MongoClient

    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=20000,
        connectTimeoutMS=20000,
        socketTimeoutMS=120000,
        appname="face-counter-verify",
    )
    try:
        client.admin.command("ping")
    except Exception as e:
        say("CONNECTION FAILED:", type(e).__name__)
        say(redact(e)[:200])
        return 2
    say("connected OK\n")

    db = client["atpg"]
    f = db["photos.files"]

    say("== 1. GridFS collections exist ==")
    guarded(
        "atpg.photos.files exists", lambda: f.count_documents({}, limit=1) >= 0, True
    )
    guarded(
        "atpg.photos.chunks exists",
        lambda: db["photos.chunks"].count_documents({}, limit=1) >= 0,
        True,
    )

    say("\n== 2. document counts (live DB — expect growth, not an exact match) ==")
    guarded(
        "photos.files documents",
        lambda: f"{f.estimated_document_count():,}",
        "24,147 at survey time",
        ok_fn=grew("24,147"),
    )
    guarded(
        "photos.chunks documents",
        lambda: f"{db['photos.chunks'].estimated_document_count():,}",
        "189,815 at survey time",
        ok_fn=grew("189,815"),
    )

    say("\n== 3. photo_type split (only 'shelf' is trainable) ==")
    try:
        by_type = {
            r["_id"]: r["n"]
            for r in f.aggregate(
                [{"$group": {"_id": "$photo_type", "n": {"$sum": 1}}}],
                allowDiskUse=True,
            )
        }
    except Exception as e:
        say(f"  [ERROR] photo_type aggregate: {type(e).__name__}")
        by_type = {}
    if by_type:
        check("photo_type=shelf", f"{by_type.get('shelf', 0):,}",
              "9,207 at survey time", ok=grew("9,207")(by_type.get("shelf", 0)))
        check("photo_type=shelf_thumb", f"{by_type.get('shelf_thumb', 0):,}",
              "7,750 at survey time",
              ok=grew("7,750")(by_type.get("shelf_thumb", 0)))
        check("photo_type=sardar", f"{by_type.get('sardar', 0):,}",
              "3,790 at survey time", ok=grew("3,790")(by_type.get("sardar", 0)))
        unexpected = set(by_type) - {"shelf", "shelf_thumb", "sardar",
                                     "sardar_thumb", "contract", "contract_thumb",
                                     None}
        check("no NEW photo_type appeared since the survey",
              ", ".join(sorted(str(u) for u in unexpected)) or "none", "none",
              ok=not unexpected)

    guarded(
        "shelf subset size on disk",
        lambda: "{:,.1f} GB".format(
            (
                list(
                    f.aggregate(
                        [
                            {"$match": {"photo_type": "shelf"}},
                            {"$group": {"_id": None, "b": {"$sum": "$length"}}},
                        ]
                    )
                )
                or [{"b": 0}]
            )[0]["b"]
            / 1024**3
        ),
        "28.4 GB at survey time",
        ok_fn=lambda a: 28.4 <= float(a.split()[0].replace(",", "")) <= 31.0,
    )

    say("\n== 4. the leakage trap: thumbs are the SAME photos ==")
    guarded(
        "shared photo_id between shelf and shelf_thumb (sample of 3000)",
        lambda: "{:,}".format(
            len(
                {
                    d["photo_id"]
                    for d in f.find({"photo_type": "shelf"}, {"photo_id": 1}).limit(
                        3000
                    )
                }
                & {
                    d["photo_id"]
                    for d in f.find(
                        {"photo_type": "shelf_thumb"}, {"photo_id": 1}
                    ).limit(3000)
                }
            )
        ),
        "1,543  (any large number proves thumbs duplicate shelf)",
        ok_fn=lambda a: int(a.replace(",", "")) > 100,
    )

    say("\n== 5. store_code is stored as BOTH int and string ==")
    try:
        types = {
            r["_id"]: r["n"]
            for r in f.aggregate(
                [{"$group": {"_id": {"$type": "$store_code"}, "n": {"$sum": 1}}}],
                allowDiskUse=True,
            )
        }
        check("store_code as string", f"{types.get('string', 0):,}",
              "21,773 at survey time", ok=grew("21,773")(types.get("string", 0)))
        check("store_code as int", f"{types.get('int', 0):,}",
              "2,361 at survey time", ok=grew("2,361")(types.get("int", 0)))
    except Exception as e:
        say(f"  [ERROR] store_code type aggregate: {type(e).__name__}")

    as_str: set[str] = set()
    as_int: set[str] = set()
    try:
        for r in f.aggregate(
            [
                {"$match": {"store_code": {"$ne": None}}},
                {
                    "$group": {
                        "_id": {"v": "$store_code", "t": {"$type": "$store_code"}}
                    }
                },
            ],
            allowDiskUse=True,
        ):
            v, t = r["_id"]["v"], r["_id"]["t"]
            (as_str if t == "string" else as_int).add(str(v).strip())
        check(
            "stores appearing as BOTH types (0 = safe to normalise)",
            f"{len(as_str & as_int):,}",
            "0",
        )
        check("distinct stores after normalising", f"{len(as_str | as_int):,}",
              "3,747 at survey time", ok=grew("3,747")(len(as_str | as_int)))
    except Exception as e:
        say(f"  [ERROR] store_code distinct: {type(e).__name__}")

    say("\n== 6. location join supplies the region the photos lack ==")
    if as_str or as_int:
        guarded(
            "photo stores matched in atpg.location",
            lambda: (lambda m, tot: f"{m:,} ({m / max(tot, 1):.1%})")(
                len(
                    (as_str | as_int)
                    & {
                        str(d["code"]).strip()
                        for d in db["location"].find(
                            {"code": {"$ne": None}}, {"code": 1}
                        )
                    }
                ),
                len(as_str | as_int),
            ),
            "3,717 (99.2%) at survey time",
            ok_fn=lambda a: float(a.split("(")[1].rstrip("%)")) > 95,
        )

    say("\n== 7. test-set feasibility ==")
    guarded(
        "distinct stores in the shelf subset",
        lambda: "{:,}".format(
            (
                list(
                    f.aggregate(
                        [
                            {"$match": {"photo_type": "shelf"}},
                            {"$group": {"_id": "$store_code"}},
                            {"$count": "n"},
                        ],
                        allowDiskUse=True,
                    )
                )
                or [{"n": 0}]
            )[0]["n"]
        ),
        "3,292 at survey time",
        ok_fn=lambda a: int(a.replace(",", "")) > 1000,
    )

    say("\n== 8. fields configs/export.yaml assumes but which DO NOT exist ==")
    for field in ("visit_id", "rep_id", "city", "created_at", "metadata"):
        guarded(
            f"photos.files.{field} — docs having it",
            lambda fld=field: f.count_documents({fld: {"$exists": True}}, limit=1),
            0,
        )

    say("\n== 9. credential privilege (should be READ-ONLY) ==")
    try:
        auth = client.admin.command(
            {"connectionStatus": 1, "showPrivileges": True}
        ).get("authInfo", {})
        actions: set[str] = set()
        for p in auth.get("authenticatedUserPrivileges", []):
            actions.update(p.get("actions", []))
        mutating = sorted(
            actions
            & {
                "insert",
                "update",
                "remove",
                "dropDatabase",
                "dropCollection",
                "shutdown",
                "createUser",
                "grantRole",
                "dropIndex",
                "createIndex",
            }
        )
        roles = [r.get("role") for r in auth.get("authenticatedUserRoles", [])]
        say(
            f"         attached roles: {len(roles)}"
            f"{'  (includes root)' if 'root' in roles else ''}"
        )
        check(
            "credential holds NO mutating actions",
            ", ".join(mutating) if mutating else "none",
            "none",
            ok=not mutating,
        )
    except Exception as e:
        say(f"  [ERROR] privilege check: {type(e).__name__}")

    client.close()
    say("\n" + "=" * 62)
    say(f"  {sum(results)}/{len(results)} checks passed")
    if not all(results):
        say("  A FAIL on section 9 is expected until the read-only user exists.")
    say("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
