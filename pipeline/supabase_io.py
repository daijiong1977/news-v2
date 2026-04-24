"""Supabase helpers — Storage uploads + DB inserts for the v2 redesign schema."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from supabase import Client, create_client

log = logging.getLogger("supa")

# Load .env once
_envp = __import__("pathlib").Path(__file__).resolve().parent.parent / ".env"
for _line in (_envp.open() if _envp.exists() else []):
    if "=" in _line and not _line.startswith("#"):
        _k, _v = _line.strip().split("=", 1)
        os.environ[_k] = _v

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
STORAGE_BUCKET = "redesign-article-images"


def client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError("SUPABASE_URL + SUPABASE_SERVICE_KEY must be set in .env")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def upload_image(local_path: Path, remote_name: str) -> str | None:
    """Upload a local file to the storage bucket. Returns public URL or None."""
    try:
        sb = client()
        data = local_path.read_bytes()
        sb.storage.from_(STORAGE_BUCKET).upload(
            remote_name,
            data,
            file_options={
                "content-type": "image/webp",
                "upsert": "true",           # string, not bool — Supabase quirk
            },
        )
        public_url = sb.storage.from_(STORAGE_BUCKET).get_public_url(remote_name)
        # Supabase appends "?" sometimes — strip
        return public_url.rstrip("?")
    except Exception as e:
        log.warning("upload_image failed %s: %s", remote_name, e)
        return None


def insert_run(row: dict[str, Any]) -> str | None:
    """Insert a redesign_runs row, return generated id."""
    try:
        sb = client()
        res = sb.table("redesign_runs").insert(row).execute()
        return res.data[0]["id"] if res.data else None
    except Exception as e:
        log.error("insert_run failed: %s", e)
        return None


def update_run(run_id: str, fields: dict[str, Any]) -> bool:
    try:
        sb = client()
        sb.table("redesign_runs").update(fields).eq("id", run_id).execute()
        return True
    except Exception as e:
        log.error("update_run failed: %s", e)
        return False


def insert_story(row: dict[str, Any]) -> str | None:
    """Insert a redesign_stories row. Upsert on (published_date, category, story_slot)."""
    try:
        sb = client()
        res = sb.table("redesign_stories").upsert(
            row, on_conflict="published_date,category,story_slot"
        ).execute()
        return res.data[0]["id"] if res.data else None
    except Exception as e:
        log.error("insert_story failed: %s", e)
        return None
