# T8a: Demo upload page at "/" (overlay only) Implementation Plan

> Part of T8 (the demo) in `.hermes/plans/2026-10-04_demo-path.md`. Not a new track.

**Goal:** Opening `http://<apps-server>:8096/` shows one plain page. You pick a
shelf photo, the page sends it to `POST /overlay` with the API key filled in
for you, and the boxed photo appears under the picker. No OpenAPI page, no
typing a key.

**Architecture:** A new `GET /` route in `src/face_counter/serving/app.py`
returns one self-contained HTML page (inline CSS + about 20 lines of JS, no
build step, no static files, no new dependencies). The page is a Python string
template in a new module `src/face_counter/serving/demo_page.py`, so the
Docker image's `COPY src` picks it up without packaging changes. The server
fills the key into the page when it renders (from `pipeline.cfg.api_key`, i.e.
`.env`), so the key is never in the repo. `/overlay` itself does not change and
still requires `X-API-Key`.

**Tech stack:** FastAPI `HTMLResponse`, vanilla `fetch` + `FormData`, and
`URL.createObjectURL` to display the returned JPEG.

---

## Decisions and risk (brief, per the user's convention)

- **The key becomes visible to anyone who loads `/`** (view-source). The demo
  port is already public and the key is already a "simple demo key", so this
  adds little exposure, but it does make `/overlay` and `/count` effectively
  open to anyone who finds the page. Mitigation is the T8 step that already
  exists: before the demo goes beyond the supervisor, set a random key, then
  close the port or put it behind Caddy (#8). Record this risk as one line in
  the runbook. Do not add anything that blocks on it.
- `/docs` stays as it is. Hiding it is out of scope (YAGNI).
- Page text is English, and the count already comes from the overlay's own
  label ("N units detected"). Open question Q1 below.
- `/count` JSON is not shown on the page. The user asked for the overlay only.

## Tasks

### Task 1: Failing tests for `GET /`

**File:** `tests/test_serving.py`. Add after `test_health_does_not_require_api_key`.

```python
def test_demo_page_served_at_root_without_key(tmp_path):
    def fake_detector(img):
        return Detections(boxes=[], scores=[], labels=[])

    p = _make_pipeline(tmp_path, fake_detector, None)
    with TestClient(app_mod.create_app(pipeline=p)) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert 'type="file"' in r.text
    assert "/overlay" in r.text


def test_demo_page_embeds_configured_key(tmp_path):
    def fake_detector(img):
        return Detections(boxes=[], scores=[], labels=[])

    p = _make_pipeline(tmp_path, fake_detector, None)
    with TestClient(app_mod.create_app(pipeline=p)) as client:
        r = client.get("/")
    assert _AUTH["X-API-Key"] in r.text
```

Run: `uv run pytest tests/test_serving.py -k demo_page -v`. Expected: 2 FAIL (404).

### Task 2: `demo_page.py` + the route

**Create:** `src/face_counter/serving/demo_page.py`. It exposes
`render(api_key: str) -> str`, which returns the page with the key inserted via
`json.dumps(api_key)` into a `<script>` constant (so quotes or `<` in a key
cannot break the page; also escape `</` with `.replace("</", "<\\/")`).
Page contents:
- Title "Shelf face counter: demo" and one sentence of caveat ("Detection
  only; counts every product, not yet faces; pilot model").
- `<input type="file" accept="image/*">` (on phones this also offers the
  camera) and a "Count" button.
- Status line: "Processing… (about N s)", then an error message on a non-200
  response (show the response's `detail`).
- `<img>` result, `max-width:100%`.
- JS: `fetch("/overlay", {method:"POST", headers:{"X-API-Key": KEY}, body: fd})`
  → `res.blob()` → `img.src = URL.createObjectURL(blob)` (revoke the previous one).

**Modify:** `src/face_counter/serving/app.py`
- Import `HTMLResponse` from `starlette.responses` and `demo_page`.
- In `create_app`, before `/health`:

```python
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def demo() -> str:
        return demo_page.render(app.state.pipeline.cfg.api_key)
```
- Update the module docstring: `GET /` is the demo page and has no key check
  of its own (it embeds the key; see the runbook's risk note).

Run: `uv run pytest tests/test_serving.py -v`. Expected: all pass.
Then `uv run pytest -q` (expect 215 passed: 213 + 2) and
`uv run ruff check src/face_counter/serving tests/test_serving.py` (no new
errors; the repo-wide count stays at the 56 pre-existing ones).

### Task 3: Try it locally in a browser

`FACE_COUNTER_HOST=127.0.0.1 uv run shelf-serve` (needs the ONNX model in
`models/`). Open `http://127.0.0.1:8000/`, upload 2 photos from
`data/label_studio/images/`, check that the overlay renders, then try an
undecodable file and check that the error shows. Take a screenshot for the
user.

Commit: `✨ feat(serving): demo upload page at / for the overlay` (gitmoji from
README's allowed list).

### Task 4: Docs

- `docs/vault/DevOps/Demo API on the apps server.md`: the "open `/`" demo
  usage, plus the one-line risk (key visible in the page source).
- `README.md` endpoint table: add the `GET /` row.
- `docs/vault/Architecture/Serving pipeline.md`: the auth line now says
  `/` is open and embeds the key.
- No IPs and no key values (public repo).

Commit: `📝 docs(serving): demo page usage and key-exposure note`.
Then `graphify update .`.

### Task 5: Redeploy on the apps server (ask before running)

Same runbook as T6: `git pull` on the server checkout, build
`face-counter-serve:<sha>`, recreate the container with the same flags
(`--env-file .env`, memory cap, read-only, models mount, `-p 8096:8000`).
Verify: `curl -s :8096/health` shows the new sha; `GET /` returns 200 HTML;
one upload through the page works from this machine.

### Task 6: Checkpoint

Update the "Current handoff" in `2026-10-04_demo-path.md` and the
`docs/PILOT.md` checkpoint: T8a done, and the next step is the existing T8
prep (pick demo photos, draft caveats, then a random key).

## Open questions

- Q1: Should the page text be English or Persian (for the supervisor)? The
  default is English. If Persian, use the ZWNJ rule for ezafe after ه.
- Q2: Accept the key-in-page exposure as it is (default), or should `/` sit
  behind a separate HTTP basic-auth password? That costs one more env var and
  is safer if the port stays public after the demo.
