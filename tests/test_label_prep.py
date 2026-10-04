"""Label Studio inputs for the pilot: labeling config, tasks with pre-drawn boxes,
and a folder of images every browser can display."""
import json
from xml.dom import minidom

import pytest
from PIL import Image

from face_counter.label_studio import prepare_label_studio as pls

PILOT = ["Kix-Max_canned", "Kix-Max_glass", "TorshX_canned", "TorshX_glass",
         "COMPETITOR_canned", "COMPETITOR_glass", "product"]


def _labels(xml):
    return {e.getAttribute("value"): e for e in minidom.parseString(xml).getElementsByTagName("Label")}


def test_short_label_list_gets_number_hotkeys_and_no_search_box():
    xml = pls.labeling_config([{"name": n} for n in PILOT])
    labels = _labels(xml)
    assert [labels[n].getAttribute("hotkey") for n in PILOT] == [str(i) for i in range(1, 8)]
    assert "<Filter" not in xml


def test_product_is_grey_so_named_boxes_stand_out():
    labels = _labels(pls.labeling_config([{"name": n} for n in PILOT]))
    assert labels["product"].getAttribute("background") == pls.UNNAMED_COLOUR
    named = {labels[n].getAttribute("background") for n in PILOT if n != "product"}
    assert pls.UNNAMED_COLOUR not in named


def test_long_label_list_keeps_the_search_box():
    xml = pls.labeling_config([{"name": f"c{i}"} for i in range(40)])
    assert "<Filter" in xml
    assert not any(e.getAttribute("hotkey") for e in _labels(xml).values())


TARGETED = ["Fizzio_glass", "Freshy-Day_glass", "Genius_glass", "Hoffenberg_canned",
            "Hoffenberg_glass", "Icy-Monkey_canned", "Icy-Monkey_glass",
            "Laimon-Fresh_canned", "Sunich-Cool_glass"]


def test_click_only_labels_leave_keys_1_to_7_where_they_were():
    classes = [{"name": n} for n in PILOT] + [{"name": n, "hotkey": False} for n in TARGETED]
    xml = pls.labeling_config(classes)
    labels = _labels(xml)
    assert [labels[n].getAttribute("hotkey") for n in PILOT] == [str(i) for i in range(1, 8)]
    assert not any(labels[n].getAttribute("hotkey") for n in TARGETED)
    assert "<Filter" not in xml


def test_every_named_label_gets_its_own_colour_and_none_looks_grey():
    classes = [{"name": n} for n in PILOT] + [{"name": n, "hotkey": False} for n in TARGETED]
    labels = _labels(pls.labeling_config(classes))
    named = [labels[n].getAttribute("background") for n in PILOT + TARGETED if n != "product"]
    assert len(set(named)) == len(named)
    assert "#a9a9a9" not in named  # indistinguishable from `product` grey


def _tasks():
    return [{"data": {"image": "/data/local-files/?d=raw/images/a.jpg", "photo_id": "a",
                      "file_name": "a.jpg", "store_id": "s1", "taken_at": ""}},
            {"data": {"image": "/data/local-files/?d=raw/images/b.jpg", "photo_id": "b",
                      "file_name": "b.heif", "store_id": "s2", "taken_at": ""}}]


def _pred(photo, label="product"):
    box = {"from_name": "label", "to_name": "image", "type": "rectanglelabels",
           "original_width": 30, "original_height": 40, "image_rotation": 0,
           "value": {"x": 1, "y": 2, "width": 3, "height": 4, "rotation": 0,
                     "rectanglelabels": [label]}}
    return {"data": {"image": f"/data/local-files/?d=raw/images/{photo}.x", "photo_id": photo},
            "predictions": [{"model_version": "yolo26l-sku110k", "score": 0.5, "result": [box]}]}


def test_predictions_are_attached_by_photo_id_keeping_task_metadata(tmp_path):
    p = tmp_path / "preds.json"
    p.write_text(json.dumps([_pred("b"), _pred("a")]), encoding="utf-8")
    out = pls.attach_predictions(_tasks(), p, {"product"})
    assert out[0]["data"]["store_id"] == "s1"          # prep metadata survives
    assert out[1]["data"]["image"].endswith("b.jpg")   # prep's image URL wins
    assert out[0]["predictions"][0]["model_version"] == "yolo26l-sku110k"


def test_a_photo_without_predictions_fails_loudly(tmp_path):
    p = tmp_path / "preds.json"
    p.write_text(json.dumps([_pred("a")]), encoding="utf-8")
    with pytest.raises(SystemExit, match="b"):
        pls.attach_predictions(_tasks(), p, {"product"})


def test_a_predicted_label_missing_from_the_config_fails_loudly(tmp_path):
    # Label Studio would silently drop those boxes.
    p = tmp_path / "preds.json"
    p.write_text(json.dumps([_pred("a", "object"), _pred("b")]), encoding="utf-8")
    with pytest.raises(SystemExit, match="object"):
        pls.attach_predictions(_tasks(), p, {"product"})


def test_staging_copies_jpegs_and_converts_the_rest_to_upright_jpegs(tmp_path):
    src, out = tmp_path / "raw", tmp_path / "images"
    src.mkdir()
    Image.new("RGB", (30, 20), "red").save(src / "a.jpg")
    # A sideways photo (EXIF orientation 6) in a container browsers can't be trusted to show.
    im = Image.new("RGB", (30, 20), "blue")
    exif = im.getexif()
    exif[0x0112] = 6
    im.save(src / "b.mpo", format="JPEG", exif=exif)

    served = pls.stage_images(["a.jpg", "b.mpo"], src, out)
    assert served == {"a.jpg": "a.jpg", "b.mpo": "b.jpg"}
    assert (out / "a.jpg").read_bytes() == (src / "a.jpg").read_bytes()
    with Image.open(out / "b.jpg") as got:
        assert got.format == "JPEG"
        assert got.size == (20, 30)                      # rotated upright, like the predictions
        assert got.getexif().get(0x0112, 1) == 1         # no second rotation in the browser


def test_staging_refuses_two_photos_with_the_same_stem(tmp_path):
    src = tmp_path / "raw"
    src.mkdir()
    for n in ("a.jpg", "a.mpo"):
        Image.new("RGB", (4, 4)).save(src / n, format="JPEG")
    with pytest.raises(SystemExit, match="a"):
        pls.stage_images(["a.jpg", "a.mpo"], src, tmp_path / "images")


def test_tasks_point_at_the_served_file_and_keep_the_original_name(tmp_path):
    lst = tmp_path / "list.txt"
    lst.write_text("a.jpg\nb.heif\n", encoding="utf-8")
    tasks = pls.build_tasks(lst, tmp_path / "no-manifest.csv", "raw/images",
                            served={"a.jpg": "a.jpg", "b.heif": "b.jpg"})
    assert tasks[1]["data"]["image"] == "/data/local-files/?d=raw/images/b.jpg"
    assert tasks[1]["data"]["file_name"] == "b.heif"
    assert tasks[1]["data"]["photo_id"] == "b"



def test_every_task_carries_a_photo_number_for_the_data_manager(tmp_path):
    # Label Studio's own ids differ per project and its list has no "No." column;
    # data.no (1..N in list order) shows as a sortable column and is what
    # review notes refer to.
    lst = tmp_path / "list.txt"
    lst.write_text("a.jpg\nb.jpg\nc.jpg\n", encoding="utf-8")
    tasks = pls.build_tasks(lst, tmp_path / "no-manifest.csv", "raw/images")
    assert [t["data"]["no"] for t in tasks] == [1, 2, 3]
