"""End-to-end check of Phase 0 on a fake MongoDB (mongomock + GridFS)."""
import csv
import io
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import mongomock
import mongomock.gridfs
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import export_photos  # noqa: E402
import make_splits  # noqa: E402
import prepare_label_studio as pls  # noqa: E402

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
        fid = fs.put(_jpeg((i * 2 % 255, 100, 150)), filename=f"shelf_{i}.jpg", contentType="image/jpeg")
        db.shelf_photos.insert_one({
            "file_id": fid, "created_at": t0 + timedelta(days=i % 30),
            "store": {"id": store, "city": ["Tehran", "Karaj", "Shiraz"][i % 3]},
            "visit_id": f"{store}-v{i // 40}", "user_id": f"rep{i % 5}",
        })
    # one broken upload and one dangling reference
    db.shelf_photos.insert_one({"file_id": fs.put(b"not an image"), "store": {"id": "S999"}})
    db.shelf_photos.insert_one({"file_id": None, "store": {"id": "S998"}})
    return db


@pytest.fixture
def fake_db():
    return build_fake_db()


def _cfg(tmp_path):
    return {
        "mongo": {"database": "field_app", "gridfs_bucket": "fs"},
        "metadata": {"source": "collection", "collection": "shelf_photos", "file_id_field": "file_id",
                     "fields": {"store_id": "store.id", "visit_id": "visit_id", "taken_at": "created_at",
                                "rep_id": "user_id", "city": "store.city"}, "query": {}},
        "export": {"out_dir": str(tmp_path / "raw"), "batch_size": 50, "throttle_seconds": 0},
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


def test_date_filter(fake_db, tmp_path):
    cfg = _cfg(tmp_path)
    cfg["export"]["date_from"] = "2026-06-21"
    manifest = export_photos.export(cfg, db=fake_db)
    assert len(list(csv.DictReader(open(manifest)))) == 40  # days 20..29 x 4 photos/day


def test_splits_no_leakage_and_stable(fake_db, tmp_path):
    manifest = export_photos.export(_cfg(tmp_path), db=fake_db)
    out = tmp_path / "splits"
    df = make_splits.make_splits(manifest, out, test_pct=20, val_pct=10, test_size=10,
                                 batch_size=25, seed=1, force=False)
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


def test_label_studio_files(fake_db, tmp_path):
    manifest = export_photos.export(_cfg(tmp_path), db=fake_db)
    lst = tmp_path / "list.txt"
    names = [r["file_name"] for r in csv.DictReader(open(manifest))][:5]
    lst.write_text("\n".join(names))
    classes = pls.read_classes(ROOT / "configs/classes.csv", "sku")
    xml = pls.labeling_config(classes)
    from xml.dom import minidom
    xml_dom = minidom.parseString(xml)  # valid XML
    assert len(xml_dom.getElementsByTagName("Label")) == len(classes)
    brands = [c["name"] for c in pls.read_classes(ROOT / "configs/classes.csv", "brand")]
    assert brands == ["Kix-Max", "COMPETITOR_canned", "COMPETITOR_glass"]
    tasks = pls.build_tasks(lst, manifest, "raw/images")
    assert tasks[0]["data"]["image"].startswith("/data/local-files/?d=raw/images/")
    json.dumps(tasks)
