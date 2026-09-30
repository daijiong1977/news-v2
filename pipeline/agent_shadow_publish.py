"""Explicit shadow-only deployment and public hash verification. Never production."""
import os
import subprocess

URL = "https://kidsnews-bot-shadow.vercel.app"
PROJECT = "prj_wAKQb7C37whe0Wi6BNvb5zYpbceg"
ORG = "team_q9O2RWd2qc7ZkVNtas4naaed"


def publish(root):
    from .agent_shadow import read, write
    if not (root / "done.json").exists():
        raise ValueError("finish all content steps before publishing")
    manifest = read(root / "site/shadow-run.json")
    if (root / "published.json").exists() and read(root / "published.json")["content_hash"] == manifest["content_hash"]:
        return {"ok": True, "already_done": True, "next": "verify", "url": URL}
    if (root / "deployment-request.json").exists():
        return {"ok": True, "next": "verify", "url": URL,
                "note": "deployment already submitted; verify before attempting another"}
    env = {**os.environ, "VERCEL_PROJECT_ID": PROJECT, "VERCEL_ORG_ID": ORG}
    link = root / "site/.vercel/project.json"
    if link.exists() and any(read(link).get(k) != v for k, v in (("projectId", PROJECT), ("orgId", ORG))):
        raise ValueError("site is linked to another Vercel project; refusing deployment")
    # No credential provisioning on the Bot. Maintainer or an authenticated deployment
    # connector can run this same command; missing CLI/login is a tool error, not a bypass.
    result = subprocess.run(["vercel", "deploy", "--prod", "--yes"], cwd=root / "site",
                            env=env, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError("Shadow deployment failed; check Vercel CLI/login. No production fallback.")
    write(root / "deployment-request.json", {"url": URL, "content_hash": manifest["content_hash"],
                                             "deployment_url": result.stdout.strip().splitlines()[-1]})
    return {"ok": True, "next": "verify", "url": URL}


def verify(root):
    import hashlib
    import requests
    from .agent_shadow import read, write
    from .shadow_site import CATEGORIES, LEVELS
    local = read(root / "site/shadow-run.json")
    response = requests.get(URL + "/shadow-run.json", timeout=30, headers={"Cache-Control": "no-cache"})
    response.raise_for_status()
    remote = response.json()
    if any(remote.get(k) != local[k] for k in ("content_hash", "date", "counts")):
        raise ValueError("shadow site is not this run yet; do not mark it published")
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
        raise ValueError("served shadow payload hash mismatch")
    report = {"url": URL, "content_hash": local["content_hash"], "date": local["date"],
              "counts": local["counts"], "verified_files": len(names), "production_published": False}
    write(root / "published.json", report)
    return {"ok": True, "next": "report", **report}
