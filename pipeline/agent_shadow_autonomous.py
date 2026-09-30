"""Opt-in autonomous editorial policy; production collection stays untouched.

Only metadata planning/discovery is delegated. Original evidence is fetched by
code; final drafts still use the persisted editor and second-pass review.
"""
import hashlib
import ipaddress
import socket
import time
from io import BytesIO
from dataclasses import asdict
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

from .news_sources import NewsSource

LIMITS = {"body_fetches": 36, "discovery_rounds_per_category": 2,
          "discovery_urls_per_round": 3, "max_bytes": 2_000_000,
          "redirects": 4, "fetch_seconds": 20}


class PinnedTLSAdapter(requests.adapters.HTTPAdapter):
    """Connect to a validated IP, still validate the original host's TLS cert/SNI."""
    def __init__(self, hostname):
        self.hostname = hostname
        super().__init__()

    def init_poolmanager(self, connections, maxsize, block=False, **kwargs):
        super().init_poolmanager(connections, maxsize, block=block,
                                 assert_hostname=self.hostname, server_hostname=self.hostname, **kwargs)


def validate_public_url(url):
    """No credentials, non-HTTPS, custom ports, local/private/reserved addresses."""
    parts = urlsplit(url)
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.port not in (None, 443)):
        raise ValueError("Only public HTTPS article URLs on port 443 are allowed")
    addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Private/local/reserved article address is forbidden")
    return url


def fetch_bytes(url, content_types):
    """Bounded fetch; validate every redirect and socket peer, never use proxies.

    A fresh public DNS answer is pinned to the connection while retaining TLS
    hostname checking. Feed/image fetches in the legacy mode are unaffected.
    """
    started = time.monotonic()
    with requests.Session() as session:
        session.trust_env = False
        for _ in range(LIMITS["redirects"] + 1):
            validate_public_url(url)
            parts = urlsplit(url)
            addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                raise ValueError("DNS changed to an unsafe address")
            address = addresses[0][4][0]
            netloc = f"[{address}]" if ":" in address else address
            pinned_url = urlunsplit(("https", netloc, parts.path, parts.query, ""))
            session.mount("https://", PinnedTLSAdapter(parts.hostname))
            remaining = LIMITS["fetch_seconds"] - (time.monotonic() - started)
            if remaining <= 0:
                raise ValueError("original fetch deadline exceeded")
            with session.get(pinned_url, stream=True, allow_redirects=False, timeout=(min(5, remaining), remaining),
                             headers={"User-Agent": "KidsNewsShadow/1.0", "Host": parts.netloc}) as response:
                connection = getattr(response.raw, "_connection", None)
                sock = getattr(connection, "sock", None)
                if sock is None or not ipaddress.ip_address(sock.getpeername()[0]).is_global:
                    raise ValueError("Cannot verify a public network peer")
                if response.is_redirect:
                    url = urljoin(url, response.headers["Location"])
                    continue
                response.raise_for_status()
                if not any(t in response.headers.get("Content-Type", "").lower() for t in content_types):
                    raise ValueError("Unsupported content type")
                data = bytearray()
                for chunk in response.iter_content(16384):
                    data.extend(chunk)
                    if len(data) > LIMITS["max_bytes"] or time.monotonic() - started > LIMITS["fetch_seconds"]:
                        raise ValueError("original exceeds byte/time budget")
                return bytes(data), url, response.encoding or "utf-8"
        raise ValueError("Too many original redirects")


def fetch_original(candidate):
    from .news_rss_core import extract_article_from_html
    data, url, encoding = fetch_bytes(candidate["link"], ("text/html", "application/xhtml+xml"))
    extracted = extract_article_from_html(url, data.decode(encoding, errors="replace"))
    body = extracted.get("cleaned_body") or ""
    return {**candidate, "body": body, "word_count": len(body.split()), "og_image": extracted.get("og_image"),
            "paragraphs": extracted.get("paragraphs", []), "highlights": [],
            "skip_reason": None if body else "empty original", "evidence_url": url,
            "evidence_sha256": hashlib.sha256(body.encode()).hexdigest()}


def safe_image(url, path):
    """Original-source image only, same public redirect/byte/time boundary."""
    from PIL import Image, ImageOps
    if not url:
        return None
    try:
        data, _, _ = fetch_bytes(url, ("image/",))
        with Image.open(BytesIO(data)) as image:
            if image.width * image.height > 20_000_000:
                raise ValueError("Image pixel budget exceeded")
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((1200, 1200))
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save(path, "WEBP", quality=80)
            return {"local_path": str(path), "width": image.width, "height": image.height}
    except (ValueError, OSError, requests.RequestException, Image.DecompressionBombError):
        return None


class AutonomousEditor:
    def __init__(self, root, snapshot, ask, boundary, stepwise):
        from .agent_shadow import read
        self.root, self.snapshot, self.ask = root, snapshot, ask
        self.boundary, self.stepwise = boundary, stepwise
        self.path = root / "autonomous-catalog.json"
        self.audit_path = root / "autonomous-audit.json"
        self.audit = read(self.audit_path) if self.audit_path.exists() else {
            "limits": dict(LIMITS), "discoveries": {}, "budget_exhausted": False,
            "fetch_results": {}, "mode": "autonomous"}

    def save(self):
        from .agent_shadow import write
        write(self.audit_path, self.audit)
        write(self.path, {"catalog": self.catalog, "candidates": self.snapshot["candidates"],
                          "sources": self.snapshot["sources"]})

    def plan(self):
        from .agent_shadow import read, RANK_RULES, validate_catalog
        if self.path.exists():
            data = read(self.path)
            self.catalog = data["catalog"]
            self.snapshot.update({k: data[k] for k in ("candidates", "sources")})
        else:
            ids = {x["id"] for x in self.snapshot["candidates"]}
            def check(value):
                errors = validate_catalog(value, ids)
                if not errors and any(len(v) > 6 for v in value["catalog"].values()):
                    errors.append("At most six IDs per category: three selections and three reserves")
                if not errors and any(rows for cat, rows in value["catalog"].items()
                                      if cat not in self.snapshot.get("active_categories", ("News", "Science", "Fun"))):
                    errors.append("Inactive sections must be empty; do not reroute into them")
                return errors
            rules = RANK_RULES + "\nAUTONOMOUS MODE: choose the best three per category directly, then up to three reserves. " \
                "Do NOT rank thirty or run six-choose-three. News needs one important real-world story, not just light stories. " \
                "Science needs two independent publishers. All selections must be factual and neutrally rewritable. " \
                "Only supplied metadata, no browsing yet; return an empty category if no qualified candidate exists. " \
                "Explain policy through topic/importance/risk/history fields, not invented evidence."
            rules += "\nActive sections only: " + str(self.snapshot.get("active_categories", ["News", "Science", "Fun"])) + "; inactive catalog sections must be empty."
            self.catalog = self.ask(self.root, "plan", rules,
                {k: self.snapshot[k] for k in ("date", "candidates", "history")}, check)["catalog"]
            self.save()
        self.boundary(self.root, "plan", self.stepwise)
        return self.catalog

    def pool(self, cat, target):
        from .agent_shadow import read, write
        from .full_round import _canonical_source_url
        cache_path = self.root / "bodies.json"
        cache = read(cache_path) if cache_path.exists() else {}
        index = {b["id"]: b for b in self.snapshot["candidates"]}
        past = {_canonical_source_url(r.get("source_url", "")) for r in self.snapshot["history"][cat]}
        final_urls = set(past)
        good = []
        for score in self.catalog[cat][:target]:
            b = index[score["id"]]
            if (score["history_status"] != "clear" or score["history_confidence"] < .7
                    or score["initial_risk"] >= 4 or _canonical_source_url(b["link"]) in past):
                continue
            if b["id"] not in cache:
                metrics = read(self.root / "metrics.json")
                if metrics["body_fetches"] >= LIMITS["body_fetches"]:
                    self.audit["budget_exhausted"] = True
                    break
                # Reserve budget BEFORE networking; failure/restart cannot refund it.
                metrics["body_fetches"] += 1
                write(self.root / "metrics.json", metrics)
                started = time.monotonic()
                try:
                    art = fetch_original(b)
                except (ValueError, OSError, requests.RequestException) as exc:
                    art = {**b, "body": "", "word_count": 0, "skip_reason": type(exc).__name__, "og_image": None}
                cache[b["id"]] = art
                write(cache_path, cache)
                self.audit["fetch_results"][b["id"]] = {
                    "seconds": round(time.monotonic()-started, 3), "word_count": art["word_count"],
                    "skip_reason": art.get("skip_reason"), "evidence_sha256": art.get("evidence_sha256")}
            art = cache[b["id"]]
            art = {**art, "link": art.get("evidence_url") or art["link"]}
            evidence_url = _canonical_source_url(art.get("evidence_url") or b["link"])
            if evidence_url in final_urls:
                self.audit.setdefault("url_exclusions", {})[b["id"]] = "history_or_pool_duplicate"
                continue
            if art.get("evidence_url"):
                host = urlsplit(art["evidence_url"]).hostname.lower().removeprefix("www.")
                source_name = f"verified:{host}"
                if source_name not in self.snapshot["sources"]:
                    self.snapshot["sources"][source_name] = asdict(NewsSource(
                        -len(self.snapshot["sources"])-1, source_name, f"https://{host}/", "full", 3, 0, 1, False, False))
                art = {**art, "source": source_name}
            lo, hi = (250, 1200) if cat == "Fun" else (350, 1500) if cat == "Science" else (350, 1200)
            if not art.get("skip_reason") and lo <= art["word_count"] <= hi:
                final_urls.add(evidence_url)
                good.append({**score, "category": cat, "article": art})
        self.save()
        return good

    def validate_discovery(self, value, cat):
        from .agent_shadow import validate_catalog
        if not isinstance(value, dict) or not isinstance(value.get("articles"), list):
            return ["Return articles array; empty is allowed"]
        existing = value.get("existing", [])
        if not isinstance(existing, list) or len(value["articles"]) + len(existing) > LIMITS["discovery_urls_per_round"]:
            return ["At most three candidates in articles + existing combined"]
        selected = {s["id"] for rows in self.catalog.values() for s in rows} if hasattr(self, "catalog") else set()
        available = {b["id"] for b in self.snapshot["candidates"]} - selected
        errors = validate_catalog({"catalog": {c: existing if c == cat else [] for c in ("News", "Science", "Fun")}}, available)
        if errors:
            return errors
        scores = []
        for i, item in enumerate(value["articles"]):
            allowed = {"url", "title", "topic", "importance", "initial_risk", "history_status", "history_confidence"}
            if not isinstance(item, dict) or set(item) != allowed:
                return ["Discovery fields must match schema; publisher/body are not accepted from Agent"]
            if not isinstance(item["title"], str) or not item["title"].strip():
                return ["Discovered title is required"]
            try:
                validate_public_url(item["url"])
            except (ValueError, TypeError, OSError):
                return ["Discovered article URL must be public HTTPS"]
            scores.append({"id": str(i), **{k: item[k] for k in allowed - {"url", "title"}}})
        catalog = {c: scores if c == cat else [] for c in ("News", "Science", "Fun")}
        return validate_catalog({"catalog": catalog}, {str(i) for i in range(len(scores))})

    def extend(self, cat, target, section):
        """Expand only exhausted category, preserving all accepted drafts."""
        from .agent_shadow import read, write, CATS, AnswerRejected
        from .full_round import _canonical_source_url
        if self.audit["budget_exhausted"]:
            return None
        if target < len(self.catalog[cat]):
            return min(len(self.catalog[cat]), target + 3)
        rounds = self.audit["discoveries"].get(cat, 0)
        if rounds >= LIMITS["discovery_rounds_per_category"]:
            return None
        key = f"discover-{cat}-{rounds+1}"
        accepted = [{"title": a["candidate"]["article"]["title"], "topic": a["candidate"]["topic"],
                     "source": a["candidate"]["article"]["source"]} for a in section["accepted"]]
        material = {"category": cat, "date": self.snapshot["date"], "history": self.snapshot["history"][cat],
                    "accepted": accepted, "tried": self.catalog[cat], "seeds": self.snapshot["sources"],
                    "limits": {"search_queries": 3, "pages_opened": 6, "submitted_urls": 3}}
        selected = {s["id"] for rows in self.catalog.values() for s in rows}
        material["unused_metadata"] = [{k: b[k] for k in ("id", "title", "summary", "category", "source", "link")}
                                       for b in self.snapshot["candidates"] if b["id"] not in selected]
        prompt = "DISCOVERY TASK ONLY: you may search public sources with your native search/browser tools. " \
            "Existing feeds are nice-to-have seeds, not an exclusive list. Only find articles for the requested category. " \
            "At most three searches, six opened pages and three article URLs; stop if unavailable, return articles: []. " \
            "No login, paywall bypass, downloads, code changes, source-table writes or publishing. " \
            "Follow Kids News routing/safety/neutrality: public-affairs tech News; biology Science; animal fun/fun tech Fun; " \
            "no recruiting, obituaries or shopping. Prefer an important News, second Science publisher, or engaging Fun. " \
            "Compare ONLY requested section previous-seven-day history and current accepted stories; reject same events. " \
            'Return JSON {"articles":[{"url":"https://example.com/story","title":"Title","topic":"topic",' \
            '"importance":3,"initial_risk":0,"history_status":"clear","history_confidence":0.95}]}. ' \
            "You may instead use unused_metadata IDs via optional existing:[{id,topic,importance,initial_risk,history_status,history_confidence}]. " \
            "Prefer suitable existing feed metadata before searching. At most three candidates in articles+existing COMBINED. " \
            "Do not supply body or publisher; code independently fetches evidence and derives source host."
        try:
            found = self.ask(self.root, key, prompt, material, lambda v: self.validate_discovery(v, cat))
        except AnswerRejected:
            from .agent_shadow import pin_task_answers
            pin_task_answers(self.root, key)
            found = {"articles": []}
        self.catalog[cat].extend(found.get("existing", []))
        seen = {_canonical_source_url(b["link"]) for b in self.snapshot["candidates"]}
        for item in found["articles"]:
            canonical = _canonical_source_url(item["url"])
            if canonical in seen:
                continue
            seen.add(canonical)
            host = urlsplit(item["url"]).hostname.lower().removeprefix("www.")
            sid = "d" + hashlib.sha256(canonical.encode()).hexdigest()[:16]
            source_name = f"discovered:{host}"
            self.snapshot["sources"][source_name] = asdict(NewsSource(
                -len(self.snapshot["sources"])-1, source_name, f"https://{host}/", "full", 3, 0, 1, False, False))
            self.snapshot["candidates"].append({"id": sid, "category": cat, "title": item["title"],
                "link": item["url"], "source": source_name, "summary": "", "published": ""})
            self.catalog[cat].append({"id": sid, **{k: item[k] for k in (
                "topic", "importance", "initial_risk", "history_status", "history_confidence")}})
            suggestions_path = self.root / "source-suggestions.json"
            suggestions = read(suggestions_path) if suggestions_path.exists() else []
            suggestions.append({"url": item["url"], "host": host, "category": cat,
                                "status": "temporary_not_enabled"})
            write(suggestions_path, suggestions)
        self.audit["discoveries"][cat] = rounds + 1
        self.save()
        self.boundary(self.root, key, self.stepwise)
        # Even empty rounds receive a distinct target/pool checkpoint on resume.
        return target + 3
