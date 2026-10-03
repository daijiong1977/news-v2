"""Explicit shadow-only deployment and public hash verification. Never production."""
import os
import subprocess

URL = "https://kidsnews-bot-shadow.vercel.app"
PROJECT = "prj_wAKQb7C37whe0Wi6BNvb5zYpbceg"
ORG = "team_q9O2RWd2qc7ZkVNtas4naaed"


class VerificationMismatch(ValueError):
    """Public bytes clearly do not match this run, not a transient network error."""


def publish(root, *, retry_after_failed_verify=False):
    from .agent_shadow import read, write
    if not (root / "done.json").exists():
        raise ValueError("finish all content steps before publishing")
    manifest = read(root / "site/shadow-run.json")
    if sum(manifest.get("counts", {}).values()) <= 0:
        raise ValueError("zero articles; refusing an empty shadow deployment")
    if (root / "published.json").exists() and read(root / "published.json")["content_hash"] == manifest["content_hash"]:
        return {"ok": True, "already_done": True, "next": "verify", "url": URL}
    attempt_path = root / "deployment-attempt.json"
    previous = read(attempt_path) if attempt_path.exists() else None
    failed_path = root / "verify-failure.json"
    if retry_after_failed_verify:
        failed = read(failed_path) if failed_path.exists() else {}
        if (not previous or failed.get("attempt") != previous["attempt"]
                or failed.get("content_hash") != manifest["content_hash"] or not failed.get("definitive")):
            raise ValueError("retry requires a definitive failed verify for the current deployment attempt")
    elif previous or (root / "deployment-request.json").exists():
        return {"ok": True, "next": "verify", "url": URL,
                "note": "deployment already attempted; verify before explicitly retrying"}
    env = {**os.environ, "VERCEL_PROJECT_ID": PROJECT, "VERCEL_ORG_ID": ORG}
    link = root / "site/.vercel/project.json"
    if link.exists() and any(read(link).get(k) != v for k, v in (("projectId", PROJECT), ("orgId", ORG))):
        raise ValueError("site is linked to another Vercel project; refusing deployment")
    # No credential provisioning on the Bot. Maintainer or an authenticated deployment
    # connector can run this same command; missing CLI/login is a tool error, not a bypass.
    write(attempt_path, {"attempt": (previous["attempt"] + 1) if previous else 1,
                         "content_hash": manifest["content_hash"], "url": URL})
    result = subprocess.run(["vercel", "deploy", "--prod", "--yes"], cwd=root / "site",
                            env=env, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError("Shadow deployment failed; check Vercel CLI/login. No production fallback.")
    write(root / "deployment-request.json", {"url": URL, "content_hash": manifest["content_hash"],
                                             "deployment_url": result.stdout.strip().splitlines()[-1]})
    return {"ok": True, "next": "verify", "url": URL}


def verify(root):
    from .agent_shadow import read, write
    try:
        return _verify(root)
    except VerificationMismatch as exc:
        # A timeout/network error is inconclusive and does NOT authorize resubmission.
        if (root / "deployment-attempt.json").exists():
            attempt = read(root / "deployment-attempt.json")
            write(root / "verify-failure.json", {"attempt": attempt["attempt"],
                  "content_hash": attempt["content_hash"], "definitive": True, "reason": str(exc)})
        raise


def _verify(root):
    import hashlib
    import requests
    from .agent_shadow import read, write
    from .shadow_site import CATEGORIES, LEVELS
    local = read(root / "site/shadow-run.json")
    response = requests.get(URL + "/shadow-run.json", timeout=30, headers={"Cache-Control": "no-cache"})
    response.raise_for_status()
    remote = response.json()
    if any(remote.get(k) != local[k] for k in ("content_hash", "date", "counts")):
        raise VerificationMismatch("shadow site is not this run yet; do not mark it published")
    # Verify served payloads, details AND images, not just a copied manifest.
    digest = hashlib.sha256()
    names = set()
    for cat in CATEGORIES:
        for level in LEVELS:
            relative = f"payloads/articles_{cat}_{level}.json"
            names.add(relative)
            listing = read(root / "site" / relative)
            for item in listing["articles"]:
                if level != "cn":
                    names.add(f"article_payloads/payload_{item['id']}/{level}.json")
                if item.get("image_url"):
                    names.add(item["image_url"].lstrip("/"))
    for name in sorted(names):
        result = requests.get(URL + "/" + name, timeout=30)
        result.raise_for_status()
        digest.update(name.encode() + b"\0" + result.content + b"\0")
    if digest.hexdigest() != local["content_hash"]:
        raise VerificationMismatch("served shadow payload hash mismatch")
    report = {"url": URL, "content_hash": local["content_hash"], "date": local["date"],
              "counts": local["counts"], "verified_files": len(names), "production_published": False}
    write(root / "published.json", report)
    return {"ok": True, "next": "report", **report}
