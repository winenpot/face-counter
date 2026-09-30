"""Create or update a Label Studio project from shelf-label-prep's files, over the API.

    uv run shelf-ls-setup --title pilot-gold-val --tasks <tasks.json> --config <config.xml>
    uv run shelf-ls-setup --title <title> ... --dry-run   # show what would happen, change nothing

Frozen projects (FROZEN_TITLES, e.g. the pilot test set) are refused before
anything is copied or sent.

What it does, in order (each step is safe to repeat; a second run changes nothing):

1. Photos. Copies the staged photos (`shelf-label-prep --stage-images`) to the
   server's photo folder with rsync. It only ever ADDS files: no --delete, so
   photos behind finished tasks are never removed.
2. Connection. Opens an SSH tunnel to the server and talks to Label Studio on
   the server's own 127.0.0.1, so the API token never crosses the internet in
   plain HTTP (the public port 7071 has no TLS).
3. Project. Finds the project by title. Missing: creates it with the labeling
   config and "Use predictions to prelabel tasks" on. Present with a different
   config: updates the config in place (Label Studio refuses a config that
   would orphan existing labels, and this script stops on that refusal).
4. Storage. Adds the Local files storage that lets Label Studio serve the
   photos, once. It is never synced: tasks come from step 5, not from a scan.
5. Tasks. Imports the tasks (with the detector's pre-drawn boxes), skipping
   every photo the project already has, matched by photo_id.
6. Check. Reads the project back and fetches one photo through Label Studio,
   the same way a labeler's browser does.

Where the settings come from:
- API token: LS_API_TOKEN in deploy/label-studio/.env (gitignored), or the
  LS_API_TOKEN environment variable. Create it in Label Studio: account menu >
  Account & Settings > Personal Access Token.
- Label config and tasks: data/label_studio/, written by shelf-label-prep.
- Server: the SSH host alias `atpg` from ~/.ssh/config, see --ssh-host.

What it never does: delete or rename a project, task, annotation or storage,
or touch any project other than the one named by --title.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from face_counter.utils.config import DEFAULT_LABEL_STUDIO_DIR, PROJECT_ROOT

# --- defaults: the pilot test set on the production server -------------------

# Projects this script must never write to, matched by title. The pilot test
# set's labels were frozen on 2026-09-30 as the evaluation ground truth
# (data/label_studio/FROZEN.md); a config push or an import there would
# change what every reported number is measured against.
FROZEN_TITLES = frozenset({"pilot-test-cans-glass"})

# No default project: every run names its target with --title, so a bare
# `shelf-ls-setup` can never reach the frozen test-set project.
DEFAULT_TITLE = None
DEFAULT_CONFIG = DEFAULT_LABEL_STUDIO_DIR / "labeling_config_scope.xml"
DEFAULT_TASKS = DEFAULT_LABEL_STUDIO_DIR / "tasks_test_labeling.json"
DEFAULT_IMAGES = DEFAULT_LABEL_STUDIO_DIR / "images"
DEFAULT_ENV = PROJECT_ROOT / "deploy" / "label-studio" / ".env"
DEFAULT_SSH_HOST = "atpg"
# The server's photo folder (SHELF_DATA_DIR in the server's .env) + raw/images.
DEFAULT_REMOTE_IMAGES = "/home/data/label-studio-photos/raw/images/"
# The same folder as the container sees it (docker-compose.yml mounts
# SHELF_DATA_DIR at /label-studio/files). This is what the storage entry names.
CONTAINER_IMAGES = "/label-studio/files/raw/images"
# Label Studio's port on the server itself (LS_PORT in the server's .env).
DEFAULT_REMOTE_PORT = 7071

# The value .env.example ships with; seeing it means the token was never set.
PLACEHOLDER_TOKEN = "API_ACCESS_TOKEN"


def say(msg: str) -> None:
    print(f"   {msg}", flush=True)


def step(msg: str) -> None:
    print(f"\n== {msg}", flush=True)


# --- token -------------------------------------------------------------------

def read_token(env_file: Path) -> str:
    """The API token: the LS_API_TOKEN environment variable, else the .env file.

    The value is never printed or logged anywhere by this module."""
    token = os.environ.get("LS_API_TOKEN", "").strip()
    if not token and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "LS_API_TOKEN":
                token = value.strip().strip("'\"")
    if not token or token == PLACEHOLDER_TOKEN:
        raise SystemExit(
            f"No Label Studio API token. Create a Personal Access Token in Label Studio "
            f"(account menu > Account & Settings > Personal Access Token) and put it in "
            f"{env_file} as LS_API_TOKEN=<token>. That file is gitignored.")
    return token


def is_personal_access_token(token: str) -> bool:
    """Personal access tokens are JWTs, and JWTs always start with "eyJ" (the
    base64 of '{"'). Older "legacy" tokens are 40 hex characters."""
    return token.startswith("eyJ")


# --- HTTP client ---------------------------------------------------------------

class LabelStudio:
    """A minimal Label Studio API client on the standard library.

    Personal access tokens are refresh tokens: they are exchanged for an access
    token that expires after about five minutes, so the client refreshes it
    when a request comes back 401. Legacy tokens are sent as they are."""

    def __init__(self, base_url: str, token: str):
        self.base = base_url.rstrip("/")
        self._token = token
        self._pat = is_personal_access_token(token)
        self._access: str | None = None

    def _auth_header(self) -> str:
        if not self._pat:
            return f"Token {self._token}"
        if self._access is None:
            got = self._raw("POST", "/api/token/refresh", {"refresh": self._token}, auth=False)
            self._access = got["access"]
        return f"Bearer {self._access}"

    def _raw(self, method: str, path: str, body=None, params=None, auth=True, raw=False):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if auth:
            req.add_header("Authorization", self._auth_header())
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = resp.read()
            if raw:
                return resp.status, resp.headers.get("Content-Type", ""), payload
            return json.loads(payload) if payload else None

    def request(self, method: str, path: str, body=None, params=None):
        """One API call. Retries once with a fresh access token on 401, and turns
        any other HTTP error into a readable stop, with Label Studio's own reason."""
        for attempt in (1, 2):
            try:
                return self._raw(method, path, body, params)
            except urllib.error.HTTPError as e:
                if e.code == 401 and self._pat and attempt == 1:
                    self._access = None  # expired: fetch a new one and retry
                    continue
                detail = e.read().decode("utf-8", "replace")[:800]
                raise SystemExit(f"Label Studio refused {method} {path}: HTTP {e.code}\n{detail}")
        raise AssertionError("unreachable")

    def fetch(self, path: str):
        """GET a non-JSON resource (a photo); returns (status, content type, bytes)."""
        return self._raw("GET", path, raw=True)


# --- the setup steps (each works on any object with a .request method) ---------

def _results(page):
    """Label Studio returns some lists bare and some wrapped in {"results": [...]}."""
    return page["results"] if isinstance(page, dict) else page


def ensure_project(ls, title: str, config: str, model_version: str | None) -> dict:
    """Find the project by title, creating or updating it as needed."""
    if title in FROZEN_TITLES:
        raise SystemExit(f"project {title!r} is frozen (evaluation ground truth, see "
                         f"data/label_studio/FROZEN.md); this script never writes to it. "
                         f"Use a new title for a new project.")
    projects = _results(ls.request("GET", "/api/projects/", params={"page_size": 1000}))
    same = [p for p in projects if p.get("title") == title]
    if len(same) > 1:
        raise SystemExit(f"{len(same)} projects are titled {title!r} (ids "
                         f"{[p['id'] for p in same]}); rename or delete the extra one in the UI.")
    # "Use predictions to prelabel tasks" in the UI = show_collab_predictions,
    # with model_version choosing whose predictions are shown. The config is
    # stripped because Label Studio stores it without the file's final newline;
    # comparing unstripped would "update" an unchanged config on every run.
    wanted = {"label_config": config.strip(), "show_collab_predictions": True}
    if model_version:
        wanted["model_version"] = model_version
    if not same:
        say(f"creating project {title!r}")
        return ls.request("POST", "/api/projects/", {"title": title, **wanted})
    proj = same[0]
    stale = {k: v for k, v in wanted.items()
             if (proj.get(k).strip() if isinstance(proj.get(k), str) else proj.get(k)) != v}
    if not stale:
        say(f"project {title!r} (id {proj['id']}) is already up to date")
        return proj
    say(f"updating project {title!r} (id {proj['id']}): {', '.join(sorted(stale))}")
    return ls.request("PATCH", f"/api/projects/{proj['id']}/", stale)


def ensure_storage(ls, project_id: int, path: str) -> dict:
    """Add the Local files storage entry once. Label Studio refuses to serve a
    local file that no storage entry covers, even when it is mounted."""
    existing = _results(ls.request("GET", "/api/storages/localfiles/",
                                   params={"project": project_id}))
    for s in existing:
        if s.get("path") == path:
            say(f"photo storage {path} already present (id {s['id']})")
            return s
    say(f"adding photo storage {path} (not synced: tasks come from the import)")
    return ls.request("POST", "/api/storages/localfiles/", {
        "project": project_id, "path": path, "title": "photos",
        # use_blob_urls=False: don't turn every file in the folder into a task.
        "use_blob_urls": False, "regex_filter": "",
    })


def existing_photo_ids(ls, project_id: int) -> set[str]:
    """photo_id of every task already in the project, page by page."""
    ids, page = set(), 1
    while True:
        got = ls.request("GET", "/api/tasks/",
                         params={"project": project_id, "page": page, "page_size": 100})
        tasks = got["tasks"] if isinstance(got, dict) else got
        ids |= {t["data"].get("photo_id") for t in tasks}
        total = got.get("total", len(tasks)) if isinstance(got, dict) else len(tasks)
        if not tasks or page * 100 >= total:
            return ids
        page += 1


def tasks_to_import(tasks: list[dict], existing_photo_ids: set[str]) -> list[dict]:
    """The tasks whose photo the project doesn't have yet. Matching by photo_id
    (not by Label Studio's task id) is what makes a second run import nothing."""
    seen: set[str] = set()
    for t in tasks:
        pid = t["data"]["photo_id"]
        if pid in seen:
            raise SystemExit(f"photo {pid} is listed twice in the task file")
        seen.add(pid)
    return [t for t in tasks if t["data"]["photo_id"] not in existing_photo_ids]


def import_tasks(ls, project_id: int, tasks: list[dict]) -> int:
    todo = tasks_to_import(tasks, existing_photo_ids(ls, project_id))
    if not todo:
        say("every photo is already in the project; nothing to import")
        return 0
    boxes = sum(len(p["result"]) for t in todo for p in t.get("predictions", []))
    say(f"importing {len(todo)} tasks with {boxes} pre-drawn boxes")
    ls.request("POST", f"/api/projects/{project_id}/import", todo)
    return len(todo)


def model_version_of(tasks: list[dict]) -> str | None:
    """The detector name the predictions carry, so the project shows exactly
    those. None if the tasks have no predictions."""
    versions = {p.get("model_version") for t in tasks for p in t.get("predictions", [])}
    versions.discard(None)
    if len(versions) > 1:
        raise SystemExit(f"tasks carry predictions from several models: {sorted(versions)}")
    return versions.pop() if versions else None


# --- photos and tunnel -------------------------------------------------------

def copy_photos(images: Path, ssh_host: str, remote_dir: str, dry_run: bool) -> None:
    """rsync the staged photos to the server. Adds and updates, never deletes:
    a labeled task whose photo disappears can't be reopened or reviewed."""
    if not images.is_dir() or not any(images.iterdir()):
        raise SystemExit(f"no staged photos in {images}; run shelf-label-prep --stage-images first")
    cmd = ["rsync", "-a", "--itemize-changes", "--mkpath"]
    if dry_run:
        cmd.append("--dry-run")
    cmd += [f"{images}/", f"{ssh_host}:{remote_dir}"]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    sent = [line for line in out.splitlines() if line.startswith("<f")]
    total = sum(1 for _ in images.iterdir())
    say(f"{len(sent)} of {total} photos {'would be ' if dry_run else ''}copied to "
        f"{ssh_host}:{remote_dir} (the rest were already there)")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def ssh_tunnel(ssh_host: str, remote_port: int):
    """Forward a free local port to Label Studio on the server's own 127.0.0.1.
    Yields the local base URL; the tunnel closes when the block ends."""
    port = _free_port()
    proc = subprocess.Popen(
        ["ssh", "-N", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
         "-L", f"127.0.0.1:{port}:127.0.0.1:{remote_port}", ssh_host],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 30
        while True:  # wait until the forwarded port accepts connections
            if proc.poll() is not None:
                raise SystemExit(f"SSH tunnel to {ssh_host} failed: "
                                 f"{proc.stderr.read().decode().strip()}")
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise SystemExit(f"SSH tunnel to {ssh_host} did not open in 30 s")
                time.sleep(0.5)
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# --- check ---------------------------------------------------------------------

def verify(ls, project_id: int, expected_tasks: int) -> None:
    """Read the result back the way a labeler would see it."""
    proj = ls.request("GET", f"/api/projects/{project_id}/")
    got = ls.request("GET", "/api/tasks/", params={"project": project_id, "page_size": 1})
    tasks = got["tasks"] if isinstance(got, dict) else got
    total = got.get("total", len(tasks)) if isinstance(got, dict) else len(tasks)
    if total < expected_tasks:
        raise SystemExit(f"project has {total} tasks, expected at least {expected_tasks}")
    task = ls.request("GET", f"/api/tasks/{tasks[0]['id']}/")
    boxes = sum(len(p.get("result", [])) for p in task.get("predictions", []))
    status, ctype, body = ls.fetch(task["data"]["image"])
    if status != 200 or not ctype.startswith("image/"):
        raise SystemExit(f"photo {task['data']['image']} did not load ({status} {ctype})")
    say(f"project {proj['title']!r}: {total} tasks, prelabeling "
        f"{'on' if proj.get('show_collab_predictions') else 'OFF'}")
    say(f"sample task {task['id']}: photo loads ({len(body) // 1024} KB), {boxes} pre-drawn boxes")


# --- command line --------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--title", required=True,
                    help="project title (the key: one project per title). Frozen projects "
                         f"are refused: {', '.join(sorted(FROZEN_TITLES))}")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG), help="labeling config XML")
    ap.add_argument("--tasks", default=str(DEFAULT_TASKS), help="tasks JSON from shelf-label-prep")
    ap.add_argument("--images", default=str(DEFAULT_IMAGES), help="staged photos to copy")
    ap.add_argument("--ssh-host", default=DEFAULT_SSH_HOST, help="server alias in ~/.ssh/config")
    ap.add_argument("--remote-images", default=DEFAULT_REMOTE_IMAGES, help="photo folder on the server")
    ap.add_argument("--remote-port", type=int, default=DEFAULT_REMOTE_PORT,
                    help="Label Studio's port on the server")
    ap.add_argument("--env-file", default=str(DEFAULT_ENV), help="where LS_API_TOKEN is read from")
    ap.add_argument("--skip-photos", action="store_true", help="don't copy photos (already there)")
    ap.add_argument("--dry-run", action="store_true",
                    help="copy nothing, change nothing; report what would happen")
    args = ap.parse_args()

    token = read_token(Path(args.env_file))
    if args.title in FROZEN_TITLES:  # before any photo is copied or tunnel opened
        raise SystemExit(f"project {args.title!r} is frozen (data/label_studio/FROZEN.md); "
                         "nothing was done.")
    config = Path(args.config).read_text(encoding="utf-8")
    tasks = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    model_version = model_version_of(tasks)

    step("1/6 Photos")
    if args.skip_photos:
        say("skipped (--skip-photos)")
    else:
        copy_photos(Path(args.images), args.ssh_host, args.remote_images, args.dry_run)

    step(f"2/6 Connect (SSH tunnel to {args.ssh_host}:{args.remote_port})")
    with ssh_tunnel(args.ssh_host, args.remote_port) as url:
        ls = LabelStudio(url, token)
        me = ls.request("GET", "/api/current-user/whoami")
        say(f"signed in as {me.get('email') or me.get('username')}")
        if args.dry_run:
            projects = _results(ls.request("GET", "/api/projects/", params={"page_size": 1000}))
            same = [p for p in projects if p.get("title") == args.title]
            step("Dry run: stopping here. Nothing was changed.")
            state = f"exists (id {same[0]['id']})" if same else "would be created"
            say(f"project {args.title!r}: {state}")
            say(f"{len(tasks)} tasks in {args.tasks}, predictions from {model_version}")
            return

        step("3/6 Project")
        proj = ensure_project(ls, args.title, config, model_version)
        step("4/6 Photo storage")
        ensure_storage(ls, proj["id"], CONTAINER_IMAGES)
        step("5/6 Tasks")
        import_tasks(ls, proj["id"], tasks)
        step("6/6 Check")
        verify(ls, proj["id"], len(tasks))

    print(f"\nDone. Open the project: project id {proj['id']}, "
          f"http://<server>:{args.remote_port}/projects/{proj['id']}/data", flush=True)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit(f"command failed: {' '.join(map(str, e.cmd))}\n{e.stderr or ''}")
