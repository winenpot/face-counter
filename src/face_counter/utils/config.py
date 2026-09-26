"""Shared helpers: config loading, dotted-field access, Mongo connection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# src/face_counter/utils/config.py -> utils -> face_counter -> src -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "export.yaml"
DEFAULT_CLASSES = PROJECT_ROOT / "configs" / "classes.csv"
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "raw" / "manifest.csv"
DEFAULT_IMAGES_DIR = PROJECT_ROOT / "data" / "raw" / "images"
DEFAULT_SPLITS_DIR = PROJECT_ROOT / "data" / "splits"
DEFAULT_LABEL_STUDIO_DIR = PROJECT_ROOT / "data" / "label_studio"
# Model outputs; gitignored, and what scripts/sync_from_hemin.sh pulls back.
DEFAULT_RUNS_DIR = PROJECT_ROOT / "runs"


def load_config(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_path(doc: dict, dotted: str | None, default: Any = None) -> Any:
    """Read a nested field with dot notation: get_path(d, "store.id")."""
    if not dotted:
        return default
    cur: Any = doc
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def mongo_client(cfg: dict):
    """Build a MongoClient from the env var named in the config."""
    from pymongo import MongoClient

    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass
    env_name = cfg["mongo"].get("uri_env", "MONGO_URI")
    uri = os.environ.get(env_name)
    if not uri:
        raise SystemExit(f"Set {env_name} in .env or the environment (see .env.example).")
    # Short timeouts: fail fast instead of hanging if the DB server is unreachable.
    return MongoClient(uri, serverSelectionTimeoutMS=5000, appname="shelf-detector-export")
