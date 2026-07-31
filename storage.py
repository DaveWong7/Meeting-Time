"""
Where everyone's availability lives.

Two backends, picked automatically:

1. GitHub Gist  - used when `gist_token` and `gist_id` are set in Streamlit
                  secrets. Survives app restarts and redeploys. Recommended
                  for Streamlit Community Cloud.
2. Local JSON   - the fallback. Works everywhere, but Streamlit Community
                  Cloud wipes the container's disk whenever the app sleeps
                  or redeploys, so treat it as temporary.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

import streamlit as st

GIST_FILENAME = "availability.json"
DATA_PATH = Path(os.environ.get("MEETPICKER_DATA", "data/availability.json"))

_LOCK = threading.Lock()


# --------------------------------------------------------------------------- #
# defaults
# --------------------------------------------------------------------------- #
def empty_data() -> dict[str, Any]:
    return {"version": 1, "settings": {}, "people": {}}


def _normalize(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return empty_data()
    data.setdefault("version", 1)
    data.setdefault("settings", {})
    data.setdefault("people", {})
    if not isinstance(data["people"], dict):
        data["people"] = {}
    return data


# --------------------------------------------------------------------------- #
# secrets helpers
# --------------------------------------------------------------------------- #
def _secret(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
    except Exception:
        return None
    return str(value) if value else None


def gist_config() -> tuple[str, str] | None:
    token, gist_id = _secret("gist_token"), _secret("gist_id")
    if token and gist_id:
        return token, gist_id
    return None


def backend_name() -> str:
    return "GitHub Gist" if gist_config() else "local file"


# --------------------------------------------------------------------------- #
# gist backend
# --------------------------------------------------------------------------- #
def _gist_load(token: str, gist_id: str) -> dict[str, Any]:
    import requests

    r = requests.get(
        f"https://api.github.com/gists/{gist_id}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        timeout=15,
    )
    r.raise_for_status()
    files = r.json().get("files", {})
    entry = files.get(GIST_FILENAME) or next(iter(files.values()), None)
    if not entry:
        return empty_data()
    content = entry.get("content") or ""
    if entry.get("truncated") and entry.get("raw_url"):
        content = requests.get(entry["raw_url"], timeout=15).text
    try:
        return _normalize(json.loads(content))
    except json.JSONDecodeError:
        return empty_data()


def _gist_save(token: str, gist_id: str, data: dict[str, Any]) -> None:
    import requests

    r = requests.patch(
        f"https://api.github.com/gists/{gist_id}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={"files": {GIST_FILENAME: {"content": json.dumps(data, indent=2)}}},
        timeout=15,
    )
    r.raise_for_status()


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def load_data() -> dict[str, Any]:
    cfg = gist_config()
    if cfg:
        try:
            return _gist_load(*cfg)
        except Exception as exc:  # fall back rather than crash the page
            st.warning(f"Couldn't read the shared Gist ({exc}). Using the local copy for now.")
    with _LOCK:
        if DATA_PATH.exists():
            try:
                return _normalize(json.loads(DATA_PATH.read_text("utf-8")))
            except json.JSONDecodeError:
                return empty_data()
    return empty_data()


def save_data(data: dict[str, Any]) -> None:
    data = _normalize(data)
    with _LOCK:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = DATA_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), "utf-8")
        tmp.replace(DATA_PATH)
    cfg = gist_config()
    if cfg:
        try:
            _gist_save(*cfg, data)
        except Exception as exc:
            st.error(f"Saved locally, but couldn't write to the shared Gist: {exc}")
