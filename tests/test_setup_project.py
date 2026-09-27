"""Tests for shelf-ls-setup (face_counter.label_studio.setup_project).

Everything here runs offline: the HTTP client is replaced by a small fake that
records calls and returns canned answers. The real end-to-end check is the
command itself against the server; it re-verifies its own result at the end.
"""
from __future__ import annotations

import json

import pytest

from face_counter.label_studio import setup_project as sp

# --- token -----------------------------------------------------------------

def test_token_is_read_from_the_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("LS_API_TOKEN", raising=False)
    env = tmp_path / ".env"
    env.write_text("LS_PORT=7071\n# comment\nLS_API_TOKEN='abc123'\n", encoding="utf-8")
    assert sp.read_token(env) == "abc123"


def test_environment_variable_wins_over_the_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("LS_API_TOKEN=from-file\n", encoding="utf-8")
    monkeypatch.setenv("LS_API_TOKEN", "from-env")
    assert sp.read_token(env) == "from-env"


@pytest.mark.parametrize("text", ["", "LS_API_TOKEN=\n", "LS_API_TOKEN=API_ACCESS_TOKEN\n"])
def test_missing_or_placeholder_token_stops_with_instructions(tmp_path, monkeypatch, text):
    monkeypatch.delenv("LS_API_TOKEN", raising=False)
    env = tmp_path / ".env"
    env.write_text(text, encoding="utf-8")
    with pytest.raises(SystemExit, match="Personal Access Token"):
        sp.read_token(env)


def test_token_kind_decides_the_auth_scheme():
    # Personal access tokens are JWTs (start with eyJ) and must be exchanged for
    # a short-lived access token; legacy tokens are sent as-is.
    assert sp.is_personal_access_token("eyJhbGciOi.xxx.yyy")
    assert not sp.is_personal_access_token("0123456789abcdef0123456789abcdef01234567")


# --- import plan -----------------------------------------------------------

def _task(photo):
    return {"data": {"photo_id": photo, "image": f"/data/local-files/?d=raw/images/{photo}.jpg"},
            "predictions": [{"model_version": "m", "result": []}]}


def test_only_photos_not_yet_in_the_project_are_imported():
    tasks = [_task("a"), _task("b"), _task("c")]
    todo = sp.tasks_to_import(tasks, existing_photo_ids={"b"})
    assert [t["data"]["photo_id"] for t in todo] == ["a", "c"]


def test_a_task_file_listing_a_photo_twice_is_rejected():
    with pytest.raises(SystemExit, match="twice"):
        sp.tasks_to_import([_task("a"), _task("a")], existing_photo_ids=set())


# --- against a fake Label Studio -------------------------------------------

class FakeLS:
    """Just enough of the Label Studio API for the setup flow."""

    def __init__(self, projects=None, storages=None, tasks=None):
        self.projects = projects or []
        self.storages = storages or []
        self.tasks = tasks or []
        self.calls = []

    def request(self, method, path, body=None, params=None):
        self.calls.append((method, path, body))
        if method == "GET" and path == "/api/projects/":
            return {"results": self.projects, "next": None}
        if method == "POST" and path == "/api/projects/":
            proj = {"id": 7, **body}
            self.projects.append(proj)
            return proj
        if method == "PATCH" and path.startswith("/api/projects/"):
            self.projects[0].update(body)
            return self.projects[0]
        if method == "GET" and path == "/api/storages/localfiles/":
            return self.storages
        if method == "POST" and path == "/api/storages/localfiles/":
            self.storages.append({"id": 3, **body})
            return self.storages[-1]
        if method == "GET" and path == "/api/tasks/":
            return {"tasks": self.tasks, "total": len(self.tasks)}
        if method == "POST" and path.endswith("/import"):
            self.tasks.extend(body)
            return {"task_count": len(body)}
        raise AssertionError(f"unexpected call {method} {path}")


CONFIG = '<View><Label value="product"/></View>'


def test_creates_the_project_with_prelabeling_on_when_missing():
    ls = FakeLS()
    proj = sp.ensure_project(ls, "pilot", CONFIG, "yolo26l-sku110k")
    assert proj["id"] == 7
    body = next(c[2] for c in ls.calls if c[0] == "POST")
    assert body["label_config"] == CONFIG
    # "Use predictions to prelabel tasks", with the detector's predictions selected.
    assert body["show_collab_predictions"] is True
    assert body["model_version"] == "yolo26l-sku110k"


def test_existing_project_with_the_same_config_is_left_alone():
    ls = FakeLS(projects=[{"id": 4, "title": "pilot", "label_config": CONFIG,
                           "show_collab_predictions": True, "model_version": "yolo26l-sku110k"}])
    sp.ensure_project(ls, "pilot", CONFIG, "yolo26l-sku110k")
    assert [c[0] for c in ls.calls] == ["GET"]


def test_trailing_newline_label_studio_strips_is_not_a_change():
    # Label Studio stores the config without the file's final newline.
    ls = FakeLS(projects=[{"id": 4, "title": "pilot", "label_config": CONFIG,
                           "show_collab_predictions": True, "model_version": "m"}])
    sp.ensure_project(ls, "pilot", CONFIG + "\n", "m")
    assert [c[0] for c in ls.calls] == ["GET"]


def test_existing_project_with_a_different_config_is_updated_not_duplicated():
    ls = FakeLS(projects=[{"id": 4, "title": "pilot", "label_config": "<View/>",
                           "show_collab_predictions": True, "model_version": "yolo26l-sku110k"}])
    sp.ensure_project(ls, "pilot", CONFIG, "yolo26l-sku110k")
    assert [(c[0], c[1]) for c in ls.calls] == [("GET", "/api/projects/"), ("PATCH", "/api/projects/4/")]
    assert len(ls.projects) == 1


def test_two_projects_with_the_same_title_stop_the_run():
    twins = [{"id": 1, "title": "pilot"}, {"id": 2, "title": "pilot"}]
    with pytest.raises(SystemExit, match="2 projects"):
        sp.ensure_project(FakeLS(projects=twins), "pilot", CONFIG, "m")


def test_storage_is_added_once_and_never_synced():
    ls = FakeLS()
    sp.ensure_storage(ls, 7, "/label-studio/files/raw/images")
    sp.ensure_storage(ls, 7, "/label-studio/files/raw/images")
    posts = [c for c in ls.calls if c[0] == "POST"]
    assert len(posts) == 1
    assert posts[0][2]["path"] == "/label-studio/files/raw/images"
    assert not any("sync" in c[1] for c in ls.calls)


def test_import_skips_photos_already_in_the_project():
    ls = FakeLS(tasks=[{"id": 1, "data": {"photo_id": "a"}}])
    n = sp.import_tasks(ls, 7, [_task("a"), _task("b")])
    assert n == 1
    posted = next(c[2] for c in ls.calls if c[0] == "POST")
    assert [t["data"]["photo_id"] for t in posted] == ["b"]
    json.dumps(posted)  # the body must be plain JSON
