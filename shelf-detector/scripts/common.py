"""Shared helpers: config loading, dotted-field access, Mongo connection."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


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
