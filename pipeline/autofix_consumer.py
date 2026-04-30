"""Local autofix consumer — pulls one queued item from
redesign_autofix_queue, builds a Claude Code agent prompt for it,
spawns `claude -p` to do the fix, and writes the outcome back.

Designed to be invoked by scripts/autofix-daemon.sh on the project
owner's Mac (launchd → every 30 min). Exits 0 when the queue is empty
so the daemon stays quiet.

Why a separate Python module: bash heredocs with nested $() + json
get ugly fast, and HTTP + JSON manipulation belongs in Python.

Usage:
    python -m pipeline.autofix_consumer            # one tick, real
    python -m pipeline.autofix_consumer --dry-run  # show what would run
    python -m pipeline.autofix_consumer --once     # process exactly 1 item then exit
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, parse, request

log = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
LOG_DIR = Path(os.environ.get(
    "AUTOFIX_LOG_DIR",
    str(Path.home() / "Library" / "Logs" / "kidsnews-autofix"),
))
MAX_ATTEMPTS = 3


def _h() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _http(method: str, path: str, body: dict | list | None = None,
           prefer: str | None = None, timeout: int = 30) -> tuple[int, str]:
    headers = _h()
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body).encode() if body is not None else None
    req = request.Request(
        f"{SUPABASE_URL}{path}", method=method, headers=headers, data=data,
    )
    try:
        with request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except error.HTTPError as e:
        return e.code, e.read().decode()[:1000]


def fetch_one() -> dict | None:
    """Pull the oldest fix-requested item. None if empty.

    Routine fixes run in CI via pipeline.autofix_apply (which sets
    status=resolved or status=escalated). The Mac listener ONLY acts
    on rows where the admin clicked '🤖 Fix with Claude' in a digest
    email — those are flipped to status='fix-requested' by the
    autofix-action edge function. Anything else is invisible to
    this daemon."""
    code, body = _http(
        "GET",
        "/rest/v1/redesign_autofix_queue"
        f"?status=eq.fix-requested&attempts=lt.{MAX_ATTEMPTS}"
        "&order=last_attempt_at.asc.nullsfirst&limit=1",
    )
    if code != 200:
        log.error("queue fetch failed: %s %s", code, body[:200])
        return None
    rows = json.loads(body)
    return rows[0] if rows else None


def patch(row_id: int, patch_obj: dict) -> bool:
    code, body = _http(
        "PATCH",
        f"/rest/v1/redesign_autofix_queue?id=eq.{row_id}",
        body=patch_obj, prefer="return=minimal",
    )
    if code not in (200, 204):
        log.error("patch %s failed: %s %s", row_id, code, body[:200])
        return False
    return True


PROMPT_TMPL = """\
First action: invoke `Skill: kidsnews-bugfix` via the Skill tool.
That loads the repo map, reproduce-by-bug-class playbook, page-scoped
edit rules, bug-record discipline, and the RESOLVED/ESCALATE/PROMOTABLE
output protocol. Read it BEFORE doing anything else — it tells you
exactly how to handle this row.

This is an ESCALATION. The CI auto-fixer (pipeline.autofix_apply)
already tried the routine path and failed — read the row's
`agent_log` to see what + why. Don't repeat exactly that.

  storage prefix:  {pdate}
  story id:        {sid}
  level:           {level}
  problem type:    {ptype}
  problem detail:  {detail}

Working dir: ~/myprojects/news-v2

Everything else (repo map, reproduce-by-bug-class steps, payload
schema gotchas, page-scoped edit rules, hand-off discipline,
RESOLVED/ESCALATE/PROMOTABLE output format) lives in the
kidsnews-bugfix skill. Do not improvise — the skill is the source
of truth.
"""


def build_prompt(row: dict) -> str:
    return PROMPT_TMPL.format(
        pdate=row.get("published_date"),
        sid=row.get("story_id"),
        level=row.get("level"),
        ptype=row.get("problem_type"),
        detail=json.dumps(row.get("problem_detail") or {}),
    )


def spawn_claude(prompt: str, log_path: Path, timeout_sec: int = 600) -> tuple[bool, str]:
    """Run `claude -p <prompt>` headless. Returns (ok, captured_output)."""
    if not shutil.which("claude"):
        return (False, "claude CLI not on PATH")
    cmd = [
        "claude", "-p", prompt,
        "--dangerously-skip-permissions",
        "--output-format", "text",
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout_sec, check=False,
        )
        out = (proc.stdout or "") + ("\n[STDERR]\n" + proc.stderr if proc.stderr else "")
        log_path.write_text(out)
        return (proc.returncode == 0, out)
    except subprocess.TimeoutExpired as e:
        msg = f"claude timed out after {timeout_sec}s"
        log_path.write_text(msg)
        return (False, msg)
    except Exception as e:
        msg = f"claude spawn failed: {e}"
        log_path.write_text(msg)
        return (False, msg)


def parse_outcome(output: str) -> str:
    """Parse the last non-empty line for RESOLVED / ESCALATE markers."""
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if not line:
            continue
        if line.startswith("RESOLVED:"):
            return "resolved"
        if line.startswith("ESCALATE:"):
            return "escalated"
        # First non-empty line that's neither — assume agent didn't
        # follow protocol; treat as failed.
        break
    return "failed"


def process(row: dict, dry_run: bool) -> dict:
    """Process one queue item end-to-end."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    item_log = LOG_DIR / f"item-{row['id']}.log"
    prompt = build_prompt(row)

    if dry_run:
        return {"id": row["id"], "would_run": True, "prompt_preview": prompt[:400]}

    # Mark running, bump attempts.
    patch(row["id"], {
        "status": "running",
        "last_attempt_at": datetime.now(timezone.utc).isoformat(),
        "attempts": row.get("attempts", 0) + 1,
    })

    log.info("spawning claude for item %s (%s/%s :: %s)…",
             row["id"], row["story_id"], row["level"], row["problem_type"])
    ok, output = spawn_claude(prompt, item_log)

    new_status = parse_outcome(output) if ok else "failed"
    if not ok and "RESOLVED:" in output:
        # Edge case: claude exited non-zero but printed RESOLVED before.
        new_status = "resolved"

    final_patch: dict = {
        "status": new_status,
        # Truncate to 8KB; full log is on disk under LOG_DIR.
        "agent_log": output[-8000:],
    }
    if new_status == "resolved":
        final_patch["resolved_at"] = datetime.now(timezone.utc).isoformat()
    patch(row["id"], final_patch)
    log.info("item %s → %s", row["id"], new_status)
    return {"id": row["id"], "status": new_status, "log_path": str(item_log)}


def run_one_tick(dry_run: bool, once: bool) -> dict:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY required")
    processed: list[dict] = []
    while True:
        row = fetch_one()
        if not row:
            break
        result = process(row, dry_run)
        processed.append(result)
        if once or dry_run:
            break
    return {"processed": processed, "count": len(processed)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="Pull one item but don't spawn claude or write DB")
    p.add_argument("--once", action="store_true",
                   help="Process exactly one item then exit (default: drain queue)")
    args = p.parse_args()
    out = run_one_tick(dry_run=args.dry_run, once=args.once)
    print(json.dumps(out, indent=2, default=str))
