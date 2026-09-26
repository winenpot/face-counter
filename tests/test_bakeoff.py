"""Detector bake-off plumbing, without any model: fake detectors, real outputs.

The candidates themselves (ultralytics / transformers) only run on the GPU box.
What can break silently here is everything around them: EXIF rotation, Label
Studio's percentage coordinates, and the task URL that has to match the tasks
prepare_label_studio builds for the same photos.
"""

import csv
import json

from PIL import Image

from face_counter.label_studio import prepare_label_studio as pls
from face_counter.training import detector_bakeoff as bk


def _sideways_jpeg(path, stored=(40, 20)):
    """A JPEG stored landscape with EXIF orientation 6 (displays as portrait)."""
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.new("RGB", stored, "red").save(path, "JPEG", exif=exif.tobytes())


def test_load_image_applies_exif_orientation(tmp_path):
    p = tmp_path / "side.jpg"
    _sideways_jpeg(p)
    assert Image.open(p).size == (40, 20)            # raw pixels
    assert bk.load_image(p).size == (20, 40)         # what Label Studio shows


def test_ls_prediction_is_percent_of_displayed_image():
    dets = bk.Detections(boxes=[[10, 20, 30, 60]], scores=[0.9], labels=["object"])
    pred = bk.ls_prediction(dets, width=200, height=400, model_name="m")
    (r,) = pred["result"]
    assert r["value"]["x"] == 5 and r["value"]["y"] == 5
    assert r["value"]["width"] == 10 and r["value"]["height"] == 10
    assert r["value"]["rectanglelabels"] == ["product"]
    assert (r["original_width"], r["original_height"]) == (200, 400)
    assert pred["model_version"] == "m"


def test_task_url_matches_prepare_label_studio(tmp_path):
    lst = tmp_path / "list.txt"
    lst.write_text("a b.jpg\n".replace(" ", "_"))
    (expected,) = pls.build_tasks(lst, tmp_path / "no-manifest.csv", bk.LS_URL_PREFIX)
    task = bk.ls_task("a_b.jpg", {"result": []})
    assert task["data"]["image"] == expected["data"]["image"]


def test_run_writes_counts_jsonl_overlays_and_tasks(tmp_path):
    images = tmp_path / "images"
    images.mkdir()
    _sideways_jpeg(images / "p1.jpg")
    Image.new("RGB", (30, 30), "blue").save(images / "p2.png")

    def two_boxes(img):
        # boxes in the displayed frame: p1 must arrive rotated to 20x40
        return bk.Detections(boxes=[[0, 0, 5, 5], [5, 5, img.width, img.height]],
                             scores=[0.5, 0.7], labels=["x", "x"])

    out = bk.run(["p1.jpg", "p2.png"], images, {"fake": two_boxes}, tmp_path / "out")

    with open(out / "counts.csv") as f:
        rows = list(csv.DictReader(f))
    assert [(r["file_name"], r["fake"]) for r in rows] == [("p1.jpg", "2"), ("p2.png", "2")]

    lines = [json.loads(line) for line in (out / "detections.jsonl").read_text().splitlines()]
    assert (lines[0]["width"], lines[0]["height"]) == (20, 40)
    assert lines[0]["boxes"][1] == [5, 5, 20, 40]

    tasks = json.loads((out / "ls_predictions_fake.json").read_text())
    assert len(tasks) == 2 and len(tasks[0]["predictions"][0]["result"]) == 2
    assert (out / "overlays" / "fake" / "p1.jpg").exists()
    assert (out / "overlays" / "fake" / "p2.jpg").exists()
