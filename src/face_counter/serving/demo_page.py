"""HTML page for the supervisor overlay demo (`GET /`).

Renders a single self-contained page: file picker → POST /overlay (with the
API key embedded in a JS constant) → boxed JPEG rendered in place.  No build
step, no static files, no extra dependencies.

The API key is inserted via json.dumps so quotes, angle brackets, and other
special characters cannot break out of the JS string literal.

GET / is protected by HTTP Basic Auth when ``demo_password`` is set in
ServeConfig (FACE_COUNTER_DEMO_PASSWORD in .env).  Username is ignored;
any non-empty username + the correct password grants access.  This keeps the
demo URL off casual internet scanners while the port is public.
"""

from __future__ import annotations

import json

_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Shelf face counter — demo</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1rem; color: #222; }}
    h1 {{ font-size: 1.3rem; margin-bottom: 0.25rem; }}
    .caveat {{ font-size: 0.85rem; color: #666; margin-bottom: 1.5rem; }}
    label {{ display: block; margin-bottom: 0.5rem; font-weight: 600; }}
    input[type=file] {{ display: block; margin-bottom: 0.75rem; }}
    button {{ padding: 0.5rem 1.4rem; font-size: 1rem; cursor: pointer; }}
    button:disabled {{ opacity: 0.5; cursor: default; }}
    #status {{ margin: 0.75rem 0; min-height: 1.25rem; font-size: 0.9rem; color: #555; }}
    #status.error {{ color: #c0392b; }}
    #result img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 4px; margin-top: 0.5rem; }}
  </style>
</head>
<body>
  <h1>Shelf face counter — overlay demo</h1>
  <p class="caveat">Detection only. Counts every visible product face — not yet filtered to a single facing per SKU. Pilot model; numbers have wide confidence intervals.</p>

  <label for="picker">Choose a shelf photo (JPEG or PNG, max 20 MB):</label>
  <input type="file" id="picker" accept="image/*">
  <button id="btn" onclick="run()">Count &amp; overlay</button>

  <div id="status"></div>
  <div id="result"></div>

  <script>
    const KEY = {api_key};
    let prevUrl = null;

    async function run() {{
      const picker = document.getElementById("picker");
      const btn    = document.getElementById("btn");
      const status = document.getElementById("status");
      const result = document.getElementById("result");

      if (!picker.files.length) {{
        status.className = "error";
        status.textContent = "Please select a file first.";
        return;
      }}

      btn.disabled = true;
      status.className = "";
      status.textContent = "Processing\u2026 (may take a few seconds)";
      result.innerHTML = "";
      if (prevUrl) {{ URL.revokeObjectURL(prevUrl); prevUrl = null; }}

      try {{
        const fd = new FormData();
        fd.append("file", picker.files[0]);

        const res = await fetch("/overlay", {{
          method: "POST",
          headers: {{ "X-API-Key": KEY }},
          body: fd,
        }});

        if (!res.ok) {{
          let msg = res.statusText;
          try {{ const j = await res.json(); msg = j.detail || msg; }} catch (_) {{}}
          throw new Error(msg);
        }}

        const blob = await res.blob();
        prevUrl = URL.createObjectURL(blob);
        const img = document.createElement("img");
        img.src = prevUrl;
        result.appendChild(img);
        status.textContent = "";
      }} catch (err) {{
        status.className = "error";
        status.textContent = "Error: " + err.message;
      }} finally {{
        btn.disabled = false;
      }}
    }}
  </script>
</body>
</html>
"""


def render(api_key: str) -> str:
    """Return the full HTML page with *api_key* embedded safely."""
    safe_key = json.dumps(api_key).replace("</", "<\\/")
    return _TEMPLATE.format(api_key=safe_key)
