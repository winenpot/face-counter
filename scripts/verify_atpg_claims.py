"""Re-check the numbers in docs/PHASE0_REMAINING.md against the live database.

Read-only: only count / find / aggregate are issued.

    uv run python scripts/verify_atpg_claims.py

Prints what the database says NOW next to what the survey found on 2026-09-22.
atpg is live and photos keep arriving, so "now" should be equal or higher.
A LOWER number means documents were deleted, which is worth looking into.

Nothing prints the connection string. Errors print only the exception TYPE,
because pymongo builds its error messages out of the connection string and a
full traceback would leak the server address.
"""

from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import OperationFailure

REPO = Path(__file__).resolve().parent.parent
GB = 1024**3

# Actions that a read-only user must NOT have.
WRITE_ACTIONS = {
    "insert", "update", "remove", "dropDatabase",
    "dropCollection", "shutdown", "createUser", "grantRole",
}


def mongo_uri() -> str:
    """Read MONGO_URI out of .env. The value is used, never printed."""
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("MONGO_URI="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("MONGO_URI is not set in .env")


def row(label: str, now, surveyed) -> None:
    """One aligned result line: what it is, what it is now, what I reported."""
    print(f"  {label:<44}{str(now):>16}{str(surveyed):>16}")


def main() -> int:
    client = MongoClient(
        mongo_uri(),
        serverSelectionTimeoutMS=20_000,
        socketTimeoutMS=180_000,
        appname="face-counter-verify",
    )
    db = client["atpg"]
    files = db["photos.files"]

    print(f"\n  {'':<44}{'now':>16}{'surveyed':>16}")

    # 1. The photos live in GridFS. There are far more chunks than files
    #    because GridFS splits every photo into 255KB pieces.
    row("photos.files documents", f"{files.estimated_document_count():,}", "24,147")
    row("photos.chunks documents",
        f"{db['photos.chunks'].estimated_document_count():,}", "189,815")

    # 2. Only photo_type 'shelf' is trainable. Everything else is either a
    #    different subject (sardar) or a downscaled copy (see check 3).
    by_type = {
        r["_id"]: r
        for r in files.aggregate([{"$group": {
            "_id": "$photo_type",
            "n": {"$sum": 1},
            "bytes": {"$sum": "$length"},
        }}])
    }
    for name, surveyed in (("shelf", "9,207"),
                           ("shelf_thumb", "7,750"),
                           ("sardar", "3,790")):
        row(f"photo_type={name}", f"{by_type.get(name, {}).get('n', 0):,}", surveyed)
    row("shelf subset on disk",
        f"{by_type.get('shelf', {}).get('bytes', 0) / GB:,.1f} GB", "28.4 GB")

    # 3. THE LEAKAGE TRAP. Thumbnails reuse the photo_id of a full-size photo,
    #    so exporting both types puts a photo and its own copy in the dataset.
    #    If they land in different splits, that is test-set leakage.
    full = {d["photo_id"] for d in
            files.find({"photo_type": "shelf"}, {"photo_id": 1}).limit(3000)}
    thumb = {d["photo_id"] for d in
             files.find({"photo_type": "shelf_thumb"}, {"photo_id": 1}).limit(3000)}
    row("photo_id shared by shelf+thumb (3k sample)", f"{len(full & thumb):,}", "1,543")

    # 4. store_code is a string in most documents and an int in the rest, so an
    #    equality filter silently misses whichever type it is not written for.
    types = {r["_id"]: r["n"] for r in files.aggregate(
        [{"$group": {"_id": {"$type": "$store_code"}, "n": {"$sum": 1}}}])}
    row("store_code stored as string", f"{types.get('string', 0):,}", "21,773")
    row("store_code stored as int", f"{types.get('int', 0):,}", "2,361")

    # No store uses both types, so normalising with str() cannot merge two
    # different stores into one -- which would corrupt the by-store split.
    as_str, as_int = set(), set()
    for r in files.aggregate([
        {"$match": {"store_code": {"$ne": None}}},
        {"$group": {"_id": {"v": "$store_code", "t": {"$type": "$store_code"}}}},
    ]):
        value, kind = r["_id"]["v"], r["_id"]["t"]
        (as_str if kind == "string" else as_int).add(str(value).strip())
    stores = as_str | as_int
    row("stores using BOTH types (0 = safe)", f"{len(as_str & as_int):,}", "0")
    row("distinct stores after normalising", f"{len(stores):,}", "3,747")

    # 5. Photos carry no city or region. make_splits needs one for diverse
    #    sampling, and atpg.location supplies it via code -> store_code.
    codes = {str(d["code"]).strip()
             for d in db["location"].find({"code": {"$ne": None}}, {"code": 1})}
    matched = len(stores & codes)
    row("stores matched in location",
        f"{matched:,} ({matched / max(len(stores), 1):.1%})", "3,717 (99.2%)")

    # 6. Enough distinct stores to hold out 10% as a by-store test set.
    counted = next(iter(files.aggregate([
        {"$match": {"photo_type": "shelf"}},
        {"$group": {"_id": "$store_code"}},
        {"$count": "n"},
    ])), {"n": 0})["n"]
    row("distinct stores with shelf photos", f"{counted:,}", "3,292")

    # 7. configs/export.yaml maps these field names. None of them exist.
    for field in ("visit_id", "rep_id", "city", "created_at", "metadata"):
        row(f"documents having .{field}",
            files.count_documents({field: {"$exists": True}}, limit=1), 0)

    # 8. The export is supposed to run as a read-only user.
    info = client.admin.command(
        {"connectionStatus": 1, "showPrivileges": True})["authInfo"]
    granted = set()
    for privilege in info.get("authenticatedUserPrivileges", []):
        granted.update(privilege.get("actions", []))
    can_write = sorted(granted & WRITE_ACTIONS)
    print()
    row("credential roles",
        ",".join(r["role"] for r in info["authenticatedUserRoles"]), "read")
    row("mutating actions granted", len(can_write), 0)
    if can_write:
        print(f"    -> {', '.join(can_write)}")
    print("\n  The last two lines must read 'read' and 0 once the")
    print("  shelf_reader user is in use. Until then they show the blocker.\n")

    client.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except OperationFailure as exc:
        # The server's own error. The code name is safe to show and is usually
        # all you need: AuthenticationFailed = wrong credentials in .env,
        # Unauthorized = the user lacks 'read' on atpg.
        name = (exc.details or {}).get("codeName", "unknown")
        raise SystemExit(f"MongoDB refused the request: {name} (code {exc.code})")
    except Exception as exc:
        # Connection-level errors: pymongo puts the server host and port in the
        # message, so print the type only.
        raise SystemExit(
            f"{type(exc).__name__} — message suppressed, it contains the server address"
        )
