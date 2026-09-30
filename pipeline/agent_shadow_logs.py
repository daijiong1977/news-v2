"""Best-effort private logs-branch shipping, enabled only on the Grok Bot VM."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path


def ship(root: Path):
    if not socket.gethostname().startswith("grok-bot"):
        return
    env = {**os.environ, "GIT_AUTHOR_NAME": "kidsnews-bot", "GIT_COMMITTER_NAME": "kidsnews-bot",
           "GIT_AUTHOR_EMAIL": "kidsnews-bot@users.noreply.github.com",
           "GIT_COMMITTER_EMAIL": "kidsnews-bot@users.noreply.github.com"}
    try:
        repo = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                    check=True, capture_output=True, text=True).stdout.strip())
        def git(*args, data=None, extra=None):
            return subprocess.run(["git", *args], cwd=repo, env={**env, **(extra or {})}, input=data,
                                  capture_output=True, timeout=30, check=True).stdout.decode().strip()
        # An unavailable old branch is normal for a new Bot. A rejected push is reported, never forced.
        subprocess.run(["git", "fetch", "-q", "origin", "+refs/heads/logs:refs/remotes/origin/logs"],
                       cwd=repo, capture_output=True, timeout=30)
        previous = subprocess.run(["git", "rev-parse", "-q", "--verify", "refs/remotes/origin/logs"],
                                  cwd=repo, capture_output=True, text=True).stdout.strip()
        with tempfile.TemporaryDirectory() as directory:
            extra = {"GIT_INDEX_FILE": str(Path(directory) / "index")}
            git("read-tree", previous or "--empty", extra=extra)
            for path in sorted(root.rglob("*.json")):
                if path.stat().st_size > 1_500_000:
                    continue
                relative = path.relative_to(repo / "work").as_posix()
                blob = git("hash-object", "-w", "--stdin", data=path.read_bytes())
                git("update-index", "--add", "--cacheinfo", f"100644,{blob},{relative}", extra=extra)
            tree = git("write-tree", extra=extra)
            if previous and tree == git("rev-parse", previous + "^{tree}"):
                return
            commit = git("commit-tree", tree, *(["-p", previous] if previous else []), "-m", "Kids News shadow run logs")
        git("push", "-q", "origin", f"{commit}:refs/heads/logs")
    except Exception as exc:
        print(f"shadow log shipping failed: {exc}", file=sys.stderr)
