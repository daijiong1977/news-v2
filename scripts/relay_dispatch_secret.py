"""One-time, user-authorized sealed transfer. Never output the source secret."""
import base64
import json
import os
from pathlib import Path
import urllib.request

from nacl.public import PublicKey, SealedBox

TARGET = "daijiong1977/grokbot-kidsnews"
ENVIRONMENT = "kidsnews-production"
KEY_ID = "3380204578043523366"
PUBLIC_KEY = "ZTluIF5i9eAeK4SN1Dp0bvpVIkxGcuvFe4zF64c2uS4="


def seal(token, run_id, commit):
    if not token or "\n" in token:
        raise ValueError("Missing or malformed source credential")
    encrypted = SealedBox(PublicKey(base64.b64decode(PUBLIC_KEY))).encrypt(token.encode())
    return {"target": TARGET, "environment": ENVIRONMENT,
            "secret_name": "KIDSNEWS_DISPATCH_TOKEN", "key_id": KEY_ID,
            "encrypted_value": base64.b64encode(encrypted).decode(),
            "source_run_id": run_id, "source_commit": commit}


def probe(token):
    results = {}
    for repo in ("news-v2", "kidsnews-v2"):
        path = f"repos/daijiong1977/{repo}/actions/runs?per_page=1"
        req = urllib.request.Request("https://api.github.com/" + path,
              headers={"Authorization": "Bearer " + token,
                       "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                results[repo + ":actions_read"] = response.status
        except urllib.error.HTTPError as error:
            results[repo + ":actions_read"] = error.code
        except Exception:
            results[repo + ":actions_read"] = "network_error"
    return results


def main():
    try:
        token = os.environ["RELAY_SOURCE_TOKEN"]
        capsule = seal(token, os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_SHA"])
        capsule["read_only_checks"] = probe(token)
        path = Path(os.environ["RUNNER_TEMP"]) / "sealed-dispatch.json"
        path.write_text(json.dumps(capsule))
        path.chmod(0o600)
        print(json.dumps({"sealed": True, "read_only_checks": capsule["read_only_checks"]}))
        return 0
    except Exception:
        # Neither exception payloads nor request headers may escape to logs.
        print("Sealed credential transfer failed; no credential output.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
