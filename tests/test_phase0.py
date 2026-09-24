"""End-to-end check of Phase 0 on a fake MongoDB (mongomock + GridFS)."""

import csv
import io
import json
from datetime import datetime, timedelta
from pathlib import Path

import mongomock
import mongomock.gridfs
import pytest
from PIL import Image

from face_counter.training import export_photos
from face_counter.label_studio import make_splits
from face_counter.label_studio import prepare_label_studio as pls
from face_counter.utils.config import DEFAULT_CONFIG

mongomock.gridfs.enable_gridfs_integration()


def _jpeg(color, size=(64, 48)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return buf.getvalue()


def build_fake_db():
    """120 small photos across 40 stores / 3 cities, plus one broken and one dangling upload."""
    import gridfs

    db = mongomock.MongoClient().field_app
    fs = gridfs.GridFS(db)
    t0 = datetime(2026, 6, 1)
    for i in range(120):
        store = f"S{i % 40:03d}"
        fid = fs.put(
            _jpeg((i * 2 % 255, 100, 150)),
            filename=f"shelf_{i}.jpg",
            contentType="image/jpeg",
        )
        db.shelf_photos.insert_one(
            {
                "file_id": fid,
                "created_at": t0 + timedelta(days=i % 30),
                "store": {"id": store, "city": ["Tehran", "Karaj", "Shiraz"][i % 3]},
                "visit_id": f"{store}-v{i // 40}",
                "user_id": f"rep{i % 5}",
            }
        )
    # one broken upload and one dangling reference
    db.shelf_photos.insert_one(
        {"file_id": fs.put(b"not an image"), "store": {"id": "S999"}}
    )
    db.shelf_photos.insert_one({"file_id": None, "store": {"id": "S998"}})
    return db


@pytest.fixture
def fake_db():
    return build_fake_db()


def _cfg(tmp_path):
    return {
        "mongo": {"database": "field_app", "gridfs_bucket": "fs"},
        "metadata": {
            "source": "collection",
            "collection": "shelf_photos",
            "file_id_field": "file_id",
            "fields": {
                "store_id": "store.id",
                "visit_id": "visit_id",
                "taken_at": "created_at",
                "rep_id": "user_id",
                "city": "store.city",
            },
            "query": {},
        },
        "export": {
            "out_dir": str(tmp_path / "raw"),
            "batch_size": 50,
            "throttle_seconds": 0,
        },
    }


def test_export_is_complete_and_resumable(fake_db, tmp_path):
    cfg = _cfg(tmp_path)
    manifest = export_photos.export(cfg, limit=30, db=fake_db)
    assert len(list(csv.DictReader(open(manifest)))) == 30
    export_photos.export(cfg, db=fake_db)  # resume
    rows = list(csv.DictReader(open(manifest)))
    assert len(rows) == 120  # broken + dangling skipped
    r = rows[0]
    assert r["store_id"].startswith("S") and r["city"] and r["width"] == "64"
    assert (tmp_path / "raw/images" / r["file_name"]).exists()
    assert not list((tmp_path / "raw/images").glob("*.part"))


def test_heic_photo_is_exported_not_dropped(tmp_path):
    """docs/PHASE0_REMAINING.md §2: 69 HEIC uploads were silently landing in
    bad_image because Pillow can't decode HEIC without pillow-heif. The
    opener is registered at import time (export_photos.py); confirm a HEIC
    upload actually makes it into the manifest instead of being skipped."""
    import gridfs
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (10, 20, 30)).save(buf, format="HEIF")
    heic_bytes = buf.getvalue()

    db = mongomock.MongoClient().field_app
    fs = gridfs.GridFS(db)
    fid = fs.put(heic_bytes, filename="iphone.heic", contentType="image/heic")
    db.shelf_photos.insert_one({"file_id": fid, "store": {"id": "S001"}})

    cfg = _cfg(tmp_path)
    manifest = export_photos.export(cfg, db=db)
    rows = list(csv.DictReader(open(manifest)))
    assert len(rows) == 1
    assert rows[0]["width"] == "64" and rows[0]["height"] == "48"
    assert (tmp_path / "raw/images" / rows[0]["file_name"]).exists()


def test_date_filter(fake_db, tmp_path):
    cfg = _cfg(tmp_path)
    cfg["export"]["date_from"] = "2026-06-21"
    manifest = export_photos.export(cfg, db=fake_db)
    assert len(list(csv.DictReader(open(manifest)))) == 40  # days 20..29 x 4 photos/day


def test_unedited_config_refuses_to_run(tmp_path):
    """A config with unfilled CHANGE_ME placeholders must fail loudly, not
    export 0 photos and claim success."""
    cfg = {
        "mongo": {"database": "CHANGE_ME", "gridfs_bucket": "fs"},
        "metadata": {
            "source": "collection",
            "collection": "CHANGE_ME",
            "file_id_field": "file_id",
            "fields": {},
            "query": {},
        },
        "export": {"out_dir": str(tmp_path / "raw"), "batch_size": 50},
    }
    with pytest.raises(SystemExit, match="placeholder"):
        export_photos.export(cfg)
    assert not (tmp_path / "raw" / "manifest.csv").exists()


def test_shipped_config_is_filled_in():
    """configs/export.yaml itself must point at the real atpg schema, not the
    CHANGE_ME template -- regression test for docs/PHASE0_REMAINING.md §1."""
    cfg = export_photos.load_config(DEFAULT_CONFIG)
    assert cfg["mongo"]["database"] == "atpg"
    assert cfg["mongo"]["gridfs_bucket"] == "photos"
    assert cfg["metadata"]["source"] == "gridfs"
    assert cfg["metadata"]["fields"]["store_id"] == "store_code"
    # visit_id/rep_id/city do not exist on the photo document; must stay unmapped
    assert set(cfg["metadata"]["fields"]) == {"store_id", "taken_at"}
    # only "shelf" is trainable -- shelf_thumb duplicates it, sardar is a
    # different subject; docs/PHASE0_REMAINING.md §2
    assert cfg["metadata"]["query"] == {"photo_type": "shelf"}
    # location.code -> store_code supplies the region photos don't have;
    # docs/PHASE0_REMAINING.md §1
    assert cfg["metadata"]["region_join"] == {
        "collection": "location",
        "key_field": "code",
        "value_field": "region",
    }
    # store_code is a per-visit registration code, not the store's identity;
    # the real store id only exists through this same location join.
    assert cfg["metadata"]["store_join"] == {
        "collection": "location",
        "key_field": "code",
        "value_field": "permanent_id",
    }


def test_store_join_resolves_visit_code_to_real_store(tmp_path):
    """store_code is a per-visit registration code, NOT the store's identity:
    a location.code can be reissued for the same physical store over time
    (confirmed live: one store had 5 different codes). Without the
    store_join, make_splits.py's by-store leakage guard actually groups by
    visit, so the same physical store can land in both train and test."""
    import gridfs

    db = mongomock.MongoClient().atpg
    fs = gridfs.GridFS(db, collection="photos")
    # same physical store (permanent_id "5"), two different visit codes
    fs.put(_jpeg((1, 2, 3)), filename="v1.jpg", photo_type="shelf", store_code="256")
    fs.put(_jpeg((4, 5, 6)), filename="v2.jpg", photo_type="shelf", store_code="1910")
    db.location.insert_one({"code": "256", "permanent_id": "5", "region": "R1"})
    db.location.insert_one({"code": "1910", "permanent_id": "5", "region": "R1"})
    cfg = {
        "mongo": {"database": "atpg", "gridfs_bucket": "photos"},
        "metadata": {
            "source": "gridfs",
            "fields": {"store_id": "store_code"},
            "query": {"photo_type": "shelf"},
            "store_join": {
                "collection": "location",
                "key_field": "code",
                "value_field": "permanent_id",
            },
        },
        "export": {
            "out_dir": str(tmp_path / "raw"),
            "batch_size": 50,
            "throttle_seconds": 0,
        },
    }
    manifest = export_photos.export(cfg, db=db)
    rows = list(csv.DictReader(open(manifest)))
    # both visits resolve to the SAME store, and the raw visit code survives
    # separately as visit_id -- this is what make_splits.py must group on.
    assert {r["store_id"] for r in rows} == {"5"}
    assert {r["visit_id"] for r in rows} == {"256", "1910"}


def test_int_store_code_normalised_to_string(tmp_path):
    """atpg stores store_code as str OR int (docs/PHASE0_REMAINING.md §1);
    the manifest must always get a trimmed string, never a raw int."""
    import gridfs

    db = mongomock.MongoClient().field_app
    fs = gridfs.GridFS(db)
    fid = fs.put(_jpeg((10, 20, 30)), filename="s.jpg", contentType="image/jpeg")
    db.shelf_photos.insert_one({"file_id": fid, "store": {"id": 1939}})
    cfg = _cfg(tmp_path)
    cfg["metadata"]["fields"] = {"store_id": "store.id"}
    manifest = export_photos.export(cfg, db=db)
    row = next(iter(csv.DictReader(open(manifest))))
    assert row["store_id"] == "1939"  # string, not "1939.0" or repr(1939)


def test_gridfs_source_respects_photo_type_query(tmp_path):
    """docs/PHASE0_REMAINING.md §2: exporting must only pull photo_type=shelf,
    never shelf_thumb (a downscaled copy of the same photo) or other types."""
    import gridfs

    db = mongomock.MongoClient().atpg
    fs = gridfs.GridFS(db, collection="photos")
    fs.put(_jpeg((1, 2, 3)), filename="a.jpg", photo_type="shelf", store_code="1")
    fs.put(
        _jpeg((4, 5, 6)),
        filename="a_thumb.jpg",
        photo_type="shelf_thumb",
        store_code="1",
    )
    fs.put(_jpeg((7, 8, 9)), filename="b.jpg", photo_type="sardar", store_code="2")
    cfg = {
        "mongo": {"database": "atpg", "gridfs_bucket": "photos"},
        "metadata": {
            "source": "gridfs",
            "fields": {"store_id": "store_code"},
            "query": {"photo_type": "shelf"},
        },
        "export": {
            "out_dir": str(tmp_path / "raw"),
            "batch_size": 50,
            "throttle_seconds": 0,
        },
    }
    manifest = export_photos.export(cfg, db=db)
    rows = list(csv.DictReader(open(manifest)))
    assert len(rows) == 1
    assert rows[0]["store_id"] == "1"


def test_region_join_fills_city(tmp_path):
    """docs/PHASE0_REMAINING.md §1: photos have no city/region field; it must
    come from a location.code -> store_code join, with unmatched stores
    falling back to '' rather than raising."""
    import gridfs

    db = mongomock.MongoClient().atpg
    fs = gridfs.GridFS(db, collection="photos")
    fs.put(
        _jpeg((1, 2, 3)), filename="matched.jpg", photo_type="shelf", store_code="1001"
    )
    fs.put(
        _jpeg((4, 5, 6)),
        filename="unmatched.jpg",
        photo_type="shelf",
        store_code="9999",
    )
    db.location.insert_one({"code": "1001", "region": "تهران منطقه 2"})
    cfg = {
        "mongo": {"database": "atpg", "gridfs_bucket": "photos"},
        "metadata": {
            "source": "gridfs",
            "fields": {"store_id": "store_code"},
            "query": {"photo_type": "shelf"},
            "region_join": {
                "collection": "location",
                "key_field": "code",
                "value_field": "region",
            },
        },
        "export": {
            "out_dir": str(tmp_path / "raw"),
            "batch_size": 50,
            "throttle_seconds": 0,
        },
    }
    manifest = export_photos.export(cfg, db=db)
    rows = {r["store_id"]: r for r in csv.DictReader(open(manifest))}
    assert rows["1001"]["city"] == "تهران منطقه 2"
    assert rows["9999"]["city"] == ""  # unmatched store: falls back, doesn't raise


def test_splits_no_leakage_and_stable(fake_db, tmp_path):
    manifest = export_photos.export(_cfg(tmp_path), db=fake_db)
    out = tmp_path / "splits"
    df = make_splits.make_splits(
        manifest,
        out,
        test_pct=20,
        val_pct=10,
        test_size=10,
        batch_size=25,
        seed=1,
        force=False,
    )
    assert (df.groupby("store_id")["split"].nunique() == 1).all()
    test_list = (out / "test_labeling.txt").read_text().split()
    batch_list = (out / "label_batch_01.txt").read_text().split()
    assert len(batch_list) == 25 and len(set(batch_list)) == 25
    split_of = dict(zip(df.file_name, df.split))
    assert all(split_of[n] == "test" for n in test_list)
    assert all(split_of[n] == "train" for n in batch_list)
    # re-run: same store assignment, test list untouched
    df2 = make_splits.make_splits(manifest, out, 20, 10, 10, 25, seed=99, force=False)
    assert dict(zip(df2.store_id, df2.split)) == dict(zip(df.store_id, df.split))
    assert (out / "test_labeling.txt").read_text().split() == test_list


def test_label_batches_never_repeat_a_photo(fake_db, tmp_path):
    """The one mistake that can't happen: a photo already sent to labelers
    (in any label_batch_*.txt) must never appear in a later batch, even
    after new photos are exported and shelf-splits is re-run."""
    cfg = _cfg(tmp_path)
    manifest = export_photos.export(cfg, limit=60, db=fake_db)  # partial export
    out = tmp_path / "splits"
    make_splits.make_splits(manifest, out, 20, 10, 10, 25, seed=1, force=False)
    batch_01 = set((out / "label_batch_01.txt").read_text().split())
    assert len(batch_01) == 25

    # new photos arrive: resume the export with no limit, pulling in the rest
    export_photos.export(cfg, db=fake_db)
    make_splits.make_splits(manifest, out, 20, 10, 10, 25, seed=1, force=False)

    batch_files = sorted(out.glob("label_batch_*.txt"))
    assert len(batch_files) == 2  # a real batch_02 was created from the new photos
    # batch_01 itself must be byte-identical -- never rewritten
    assert set(batch_files[0].read_text().split()) == batch_01

    all_sent: list[str] = []
    for f in batch_files:
        all_sent.extend(f.read_text().split())
    # the core guarantee: no filename appears in more than one batch file
    assert len(all_sent) == len(set(all_sent))
    batch_02 = set(batch_files[1].read_text().split())
    assert batch_02.isdisjoint(batch_01)


def test_label_studio_files(fake_db, tmp_path):
    manifest = export_photos.export(_cfg(tmp_path), db=fake_db)
    lst = tmp_path / "list.txt"
    names = [r["file_name"] for r in csv.DictReader(open(manifest))][:5]
    lst.write_text("\n".join(names))

    # Own fixture, independent of whatever real class list is currently
    # shipped in configs/classes.csv -- that file is regenerated from a
    # real (gitignored) sales invoice and its exact contents are not
    # something this test should depend on.
    classes_csv = tmp_path / "classes.csv"
    classes_csv.write_text(
        "class_name,brand,category,sku,is_ours\n"
        "Kix-Max_canned_blueberry,Kix-Max,canned,blueberry,1\n"
        "Kix-Max_canned_strawberry,Kix-Max,canned,strawberry,1\n"
        "Kix-Max_glass_blueberry,Kix-Max,glass,blueberry,1\n"
        "COMPETITOR_canned,COMPETITOR,canned,,0\n"
        "COMPETITOR_glass,COMPETITOR,glass,,0\n"
    )
    classes = pls.read_classes(classes_csv, "sku")
    xml = pls.labeling_config(classes)
    from xml.dom import minidom

    xml_dom = minidom.parseString(xml)  # valid XML
    assert len(xml_dom.getElementsByTagName("Label")) == len(classes)
    brands = [c["name"] for c in pls.read_classes(classes_csv, "brand")]
    assert brands == ["Kix-Max", "COMPETITOR_canned", "COMPETITOR_glass"]
    tasks = pls.build_tasks(lst, manifest, "raw/images")
    assert tasks[0]["data"]["image"].startswith("/data/local-files/?d=raw/images/")
    json.dumps(tasks)
