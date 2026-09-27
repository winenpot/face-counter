"""Static checks on scripts/deploy_label_studio.sh and its git reminder hook.

The deploy script runs against a shared production server whose Docker volumes
hold every annotation ever made. These tests don't deploy anything (that needs
Docker and SSH; see deploy/label-studio/README.md, "Deploying changes", for the
manual end-to-end test). They pin the properties that must never regress:

- the script parses as bash;
- it contains no command that can delete volumes, containers' data, or files
  on the server (`down`, `volume rm`, `prune`, `rsync --delete`, `rm`);
- it never copies the server's `.env` (secrets live only there);
- the post-commit reminder hook exists and is executable.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deploy_label_studio.sh"
HOOK = ROOT / ".githooks" / "post-commit"


def _code_lines(path: Path) -> list[str]:
    """The script's lines with comments removed, so the warnings it prints and
    the explanations in its comments don't trip the forbidden-command checks."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        out.append(line)
    return out


def test_script_exists_and_is_executable():
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK)


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
def test_script_is_valid_bash():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


@pytest.mark.parametrize("pattern", [
    r"\bcompose\b[^\n]*\bdown\b",   # `down` removes containers; `down -v` removes the labels
    r"\bvolume\s+(rm|prune)\b",
    r"\bprune\b",
    r"--delete",                     # rsync --delete would remove files on the server
    r"\brm\s",                       # no file deletion at all
    r"--volumes",
])
def test_script_has_no_destructive_command(pattern):
    # echo/printf lines are messages to the user, not commands.
    offenders = [l for l in _code_lines(SCRIPT)
                 if re.search(pattern, l) and not re.match(r"\s*(echo|printf|say|warn|die)\b", l.strip())]
    assert offenders == [], f"forbidden command in deploy script: {offenders}"


def test_rsync_always_excludes_the_server_env_file():
    rsyncs = [l for l in _code_lines(SCRIPT) if re.search(r"^\s*rsync\b", l)]
    assert rsyncs, "the script should sync with rsync"
    for line in rsyncs:
        assert "--exclude=.env" in line, line


def test_post_commit_hook_is_executable():
    assert HOOK.is_file()
    assert os.access(HOOK, os.X_OK)
    assert "deploy/label-studio" in HOOK.read_text(encoding="utf-8")
