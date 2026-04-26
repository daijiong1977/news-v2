// Verify-source — render a 3-article preview for an RSS source, in
// the edge function itself. No GitHub Actions, no PAT.
//
// Auth: caller's JWT must belong to a user listed in
// public.redesign_admin_users (same gate the admin page uses).
//
// Flow:
//   1. Look up the source row by id.
//   2. Fetch its RSS feed; pull top 3 items via a tiny regex parser
//      (good enough for RSS/Atom — we only need title/link/pubDate/desc).
//   3. For each item: fetch the article URL, extract og:image /
//      og:title / og:description from the response HTML. Strip
//      banner-crop params from og:image (the cleaner.py gotcha:
//      Squarespace / IEEE Spectrum CMSes embed `coordinates=` /
//      `rect=` / `crop=` to force 2:1 share crops that chop heads).
//   4. Render a self-contained HTML preview and return it. Also
//      stamp last_verified_at on the source row.
//
// The admin modal just renders the returned HTML in an iframe via
// the srcdoc attribute. No storage upload needed — the preview is
// ephemeral by design (run again to refresh).

// deno-lint-ignore-file no-explicit-any
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { DOMParser, initParser, type Element } from "https://deno.land/x/deno_dom@v0.1.49/deno-dom-wasm-noinit.ts";

// deno-dom WASM must be initialised once before any DOMParser use. Using the
// noinit variant (rather than the auto-init one) gives us a stable startup
// path on Supabase Edge — the auto-init variant has flaky cold-start behaviour.
let _domReady: Promise<void> | null = null;
function ensureDom(): Promise<void> {
  if (!_domReady) _domReady = initParser();
  return _domReady;
}

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const ANON_KEY     = Deno.env.get("SUPABASE_ANON_KEY") ?? "";

const sb = createClient(SUPABASE_URL, SERVICE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const UA = "kidsnews-verify/1.0 (+https://kidsnews.21mins.com)";

async function requireAdmin(req: Request): Promise<string> {
  const auth = req.headers.get("authorization") || "";
  if (!auth.startsWith("Bearer ")) throw new Error("Sign-in required");
  const token = auth.slice("Bearer ".length);
  const ub = createClient(SUPABASE_URL, ANON_KEY, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { headers: { Authorization: `Bearer ${token}` } },
  });
  const { data: { user }, error } = await ub.auth.getUser(token);
  if (error || !user || !user.email) throw new Error("Auth failed");
  const { data: row } = await sb.from("redesign_admin_users").select("email").eq("email", user.email).maybeSingle();
  if (!row) throw new Error("Not an admin");
  return user.email;
}

// ── RSS / Atom parsing ─────────────────────────────────────────────
// Regex-only — no DOMParser. We're not building an RSS reader, just
// peeking at the latest 3 entries. Handles both <item>...</item> and
// Atom's <entry>...</entry>.
function unwrapCdata(s: string): string {
  return s.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1").trim();
}

function decodeEntities(s: string): string {
  return s
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&nbsp;/g, " ");
}

function stripTags(s: string): string {
  return s.replace(/<[^>]+>/g, "").trim();
}

function parseFeed(xml: string, max = 3): { title: string; link: string; pubDate: string; description: string }[] {
  const block = /<(item|entry)\b[\s\S]*?<\/\1>/g;
  const out: any[] = [];
  let m: RegExpExecArray | null;
  while ((m = block.exec(xml)) && out.length < max) {
    const seg = m[0];
    const title = unwrapCdata((seg.match(/<title[^>]*>([\s\S]*?)<\/title>/i) || [])[1] || "");
    let link = (seg.match(/<link[^>]*?href=["']([^"']+)["']/i) || [])[1]
            || (seg.match(/<link[^>]*>([\s\S]*?)<\/link>/i) || [])[1]
            || "";
    link = unwrapCdata(link);
    const pubDate = unwrapCdata(
      (seg.match(/<(?:pubDate|published|updated|dc:date)[^>]*>([\s\S]*?)<\/(?:pubDate|published|updated|dc:date)>/i) || [])[1] || ""
    );
    let description = unwrapCdata(
      (seg.match(/<(?:description|summary|content[^>]*?)[^>]*>([\s\S]*?)<\/(?:description|summary|content)>/i) || [])[1] || ""
    );
    description = stripTags(decodeEntities(description)).slice(0, 600);
    out.push({
      title: stripTags(decodeEntities(title)),
      link,
      pubDate,
      description,
    });
  }
  return out;
}

// ── og: meta extraction ────────────────────────────────────────────
function extractOg(html: string): { image: string; title: string; description: string; siteName: string } {
  const grab = (key: string) => {
    const re1 = new RegExp(`<meta\\s+[^>]*?(?:property|name)\\s*=\\s*["']og:${key}["'][^>]*?content\\s*=\\s*["']([^"']+)["']`, "i");
    const re2 = new RegExp(`<meta\\s+[^>]*?content\\s*=\\s*["']([^"']+)["'][^>]*?(?:property|name)\\s*=\\s*["']og:${key}["']`, "i");
    return (html.match(re1) || html.match(re2) || [])[1] || "";
  };
  return {
    image: stripBannerCrop(grab("image")),
    title: decodeEntities(grab("title")),
    description: decodeEntities(grab("description")),
    siteName: decodeEntities(grab("site_name")),
  };
}

// ── Article body extraction ────────────────────────────────────────
// Mirror of pipeline/cleaner.py · _extract_paragraphs_from_soup +
// clean_paragraphs. We use deno-dom (WASM) so the same paragraph
// selector chain produces the same body the pipeline will see when
// it actually runs the source — verify word counts must predict
// what the LLM rewriter gets, not give a different signal.
//
// Word count is the key quality signal: 0-100 words = headline-only
// feed (skip), 200-500 = lightweight, 500-1500 = decent middle-school
// reading material, 1500+ = full longform. The excerpt is the first
// ~80 words so the editor can eyeball whether extraction worked.

const _PARA_SELECTORS = [
  "article p",
  "main p",
  "div.article p",
  "div[role='main'] p",
  "div.body-text p",
  "div.post-body p",
  "div.entry-content p",
  "div.article-body p",
  "div.articleBody p",
  "div.content p",
].join(", ");

// Drop AI-authoring disclaimers (USAToday/Gannett style).
const _AI_DISCLAIMER_SIGNALS = [
  "with the assistance of Artificial Intelligence",
  "with the assistance of artificial intelligence",
  "assisted by AI",
  "AI-generated",
  "cm.usatoday.com/ethical-conduct",
  "ethical-conduct",
  "Gannett",
];
// Drop social-share lone-paragraph lines.
const _SOCIAL_SHARE_RE = /^\s*(\[Facebook\]\([^)]+\)|\[Twitter\]\([^)]+\)|\[X\]\([^)]+\)|Email|\[Email\]\([^)]+\))(?:[\s,]+(?:\[Facebook\]\([^)]+\)|\[Twitter\]\([^)]+\)|\[X\]\([^)]+\)|Email|\[Email\]\([^)]+\)))*\s*$/;
// Drop "Read More:" / "Watch:" / "Notice:" boilerplate prefixes.
const _TRIM_PREFIX_RE = /^(?:Read More:|READ MORE:|Watch:|WATCH:|Notice:|NOTICE:)/;

function _isJunkParagraph(text: string): boolean {
  if (_AI_DISCLAIMER_SIGNALS.some(sig => text.includes(sig))) return true;
  if (_SOCIAL_SHARE_RE.test(text)) return true;
  if (_TRIM_PREFIX_RE.test(text)) return true;
  if (text.includes("Support trusted journalism")) return true;
  if (text.includes("Support Provided By:")) return true;
  return false;
}

function _normaliseText(s: string): string {
  return decodeEntities(s).replace(/\s+/g, " ").trim();
}

function _excerpt(text: string, maxWords = 80): string {
  const arr = text.split(/\s+/).filter(Boolean);
  return arr.slice(0, maxWords).join(" ") + (arr.length > maxWords ? "…" : "");
}

function _countWords(text: string): number {
  if (!text) return 0;
  return text.split(/\s+/).filter(Boolean).length;
}

// Extract via the BS4-equivalent paragraph chain. Returns the joined body
// or "" if the DOM strategy didn't find ≥3 substantial paragraphs.
function _extractParagraphs(doc: any): { text: string; method: string } {
  // Drop scripts/styles/noscript first (matches BS4 .decompose() in pipeline).
  for (const sel of ["script", "style", "noscript"]) {
    doc.querySelectorAll(sel).forEach((n: any) => n.remove?.() ?? n.parentNode?.removeChild?.(n));
  }

  let containerHits: Element[] = Array.from(doc.querySelectorAll(_PARA_SELECTORS)) as Element[];
  let method = "container-p";
  if (containerHits.length < 3) {
    containerHits = Array.from(doc.querySelectorAll("p")) as Element[];
    method = "all-p";
  }

  // Pull text, trim, length-filter (>10 chars), same as pipeline.
  const raw: string[] = [];
  for (const p of containerHits) {
    const text = _normaliseText(p.textContent || "");
    if (text && text.length > 10) raw.push(text);
  }

  // Skip leading short paragraphs (byline territory) — first paragraph >50.
  let start = 0;
  for (let i = 0; i < raw.length; i++) {
    if (raw[i].length > 50) { start = i; break; }
  }
  const filtered = raw.slice(start);

  // Drop boilerplate, cap at 20 paragraphs (same as pipeline).
  const cleaned = filtered.filter(p => !_isJunkParagraph(p)).slice(0, 20);
  return { text: cleaned.join("\n\n"), method };
}

async function extractArticleBody(html: string): Promise<{ words: number; excerpt: string; method: string }> {
  if (!html) return { words: 0, excerpt: "", method: "none" };
  await ensureDom();
  let doc: any;
  try {
    doc = new DOMParser().parseFromString(html, "text/html");
  } catch {
    return { words: 0, excerpt: "", method: "parse-error" };
  }
  if (!doc) return { words: 0, excerpt: "", method: "parse-error" };

  // Primary: BS4-equivalent paragraph extraction.
  const dom = _extractParagraphs(doc);
  let words = _countWords(dom.text);
  if (words >= 50) {
    return { words, excerpt: _excerpt(dom.text), method: dom.method };
  }

  // Fallback: JSON-LD articleBody (NYT, NPR, etc. expose full text here).
  const ldNodes = Array.from(doc.querySelectorAll('script[type="application/ld+json"]')) as Element[];
  for (const node of ldNodes) {
    try {
      const obj = JSON.parse(node.textContent || "");
      const arr = Array.isArray(obj) ? obj : (obj["@graph"] && Array.isArray(obj["@graph"]) ? obj["@graph"] : [obj]);
      for (const item of arr) {
        const body = item && item.articleBody;
        if (typeof body === "string" && body.trim().length > 200) {
          const text = _normaliseText(body);
          words = _countWords(text);
          if (words >= 50) return { words, excerpt: _excerpt(text), method: "json-ld" };
        }
      }
    } catch { /* invalid JSON; continue */ }
  }

  // If dom returned something tiny, prefer it over nothing rather than 0.
  if (dom.text) {
    return { words: _countWords(dom.text), excerpt: _excerpt(dom.text), method: dom.method };
  }
  return { words: 0, excerpt: "", method: "none" };
}

// Mirror of pipeline/cleaner.py · _strip_banner_crop_params(). Some
// CMSes pre-crop og:image to a 2:1 social banner via query params,
// chopping heads off portraits. Always strip those before showing.
function stripBannerCrop(url: string): string {
  if (!url) return url;
  try {
    const u = new URL(url);
    ["coordinates", "rect", "crop", "g_focus", "g"].forEach(p => u.searchParams.delete(p));
    return u.toString();
  } catch {
    return url;
  }
}

async function fetchTextWithTimeout(url: string, ms = 8000): Promise<string> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    const r = await fetch(url, { headers: { "User-Agent": UA, "Accept": "text/html,*/*;q=0.8" }, signal: ctrl.signal });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.text();
  } finally {
    clearTimeout(t);
  }
}

// ── Render a self-contained HTML preview ───────────────────────────
function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]!));
}

// Render ONE source's preview as a fragment (sub-doc). Used standalone
// for id:N and concatenated for category:X.
// Word-count badge for body length. Color-coded: red < 200 (headline-
// only feed; can't ship to a kid LLM rewriter that needs ≥300 words),
// orange 200-499 (lightweight; will work but wears thin), green ≥ 500
// (real article — what we want for the daily pipeline).
function wcBadge(w: number, method: string): string {
  if (!w) return `<span style="display:inline-block;padding:2px 8px;border-radius:999px;font-size:10.5px;font-weight:800;background:#ffe4e4;color:#b22525;letter-spacing:.04em;">no body extracted</span>`;
  let bg = "#d4f3ef", fg = "#0e8d82";   // green
  if (w < 200) { bg = "#ffe4e4"; fg = "#b22525"; }
  else if (w < 500) { bg = "#fff4c2"; fg = "#8a6d00"; }
  return `<span style="display:inline-block;padding:2px 8px;border-radius:999px;font-size:10.5px;font-weight:800;background:${bg};color:${fg};letter-spacing:.04em;" title="extracted via ${escapeHtml(method)}">${w} words · ${escapeHtml(method)}</span>`;
}

function renderSourceBlock(source: any, generatedAt: string, articles: any[], topError: string | null = null): string {
  // Source-level summary: average word count if we have body data.
  const withBody = articles.filter((a: any) => a.body && typeof a.body.words === "number");
  const totalWords = withBody.reduce((s: number, a: any) => s + a.body.words, 0);
  const avgWords = withBody.length ? Math.round(totalWords / withBody.length) : 0;
  const summaryBlurb = withBody.length
    ? `<div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:12px;color:#6b5c80;">
        <span><b>Body extraction:</b></span>
        <span>${withBody.length}/${articles.length} extracted</span>
        <span>·</span>
        <span>avg <b>${avgWords}</b> words</span>
        <span>·</span>
        <span>total ${totalWords}</span>
        ${avgWords < 300
          ? `<span style="color:#b22525;font-weight:700;">⚠ avg below 300 — may not meet pipeline min_body_words</span>`
          : avgWords >= 800
          ? `<span style="color:#0e8d82;font-weight:700;">✓ healthy</span>`
          : `<span style="color:#8a6d00;">✓ usable</span>`}
      </div>`
    : "";

  const cards = articles.map((a: any, i: number) => `
    <article style="background:#fff;border:1px solid #e2dccc;border-radius:14px;overflow:hidden;margin-bottom:14px;display:grid;grid-template-columns:1fr 2fr;gap:0;">
      ${a.og.image
        ? `<div style="background:url('${escapeHtml(a.og.image)}') center/cover, #f0e8d8; min-height:200px;"></div>`
        : `<div style="background:#f0e8d8;min-height:200px;display:flex;align-items:center;justify-content:center;color:#9a8d7a;font-size:13px;">no og:image</div>`}
      <div style="padding:14px 18px;">
        <div style="font-size:11px;color:#9a8d7a;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
          <span>Article ${i + 1}${a.pubDate ? " · " + escapeHtml(a.pubDate) : ""}</span>
          ${a.body ? wcBadge(a.body.words, a.body.method) : ""}
        </div>
        <h3 style="font-family:Georgia,serif;font-size:18px;font-weight:900;color:#1b1230;margin:0 0 8px;line-height:1.25;">
          ${escapeHtml(a.og.title || a.title || "(untitled)")}
        </h3>
        <p style="font-size:13.5px;color:#3a2a4a;line-height:1.55;margin:0 0 10px;">
          ${escapeHtml(a.og.description || a.feedDescription || "(no description)").slice(0, 360)}
        </p>
        ${a.body && a.body.words >= 50
          ? `<details style="margin:6px 0 8px;font-size:12.5px;color:#3a2a4a;line-height:1.55;">
              <summary style="cursor:pointer;color:#1f5fd1;font-weight:700;">show extracted body excerpt (first ${Math.min(80, a.body.words)} of ${a.body.words} words)</summary>
              <div style="margin-top:6px;padding:10px 12px;background:#fff9ef;border:1px dashed #e2dccc;border-radius:8px;">${escapeHtml(a.body.excerpt)}</div>
            </details>`
          : ""}
        ${a.error ? `<div style="font-size:12px;color:#b22525;margin-bottom:8px;">⚠ ${escapeHtml(a.error)}</div>` : ""}
        <div style="font-size:11px;color:#9a8d7a;">
          ${a.og.siteName ? escapeHtml(a.og.siteName) + " · " : ""}
          <a href="${escapeHtml(a.link)}" target="_blank" rel="noopener" style="color:#1f5fd1;">open ↗</a>
          ${a.og.image ? ` · <a href="${escapeHtml(a.og.image)}" target="_blank" rel="noopener" style="color:#9a8d7a;">img ↗</a>` : ""}
        </div>
      </div>
    </article>
  `).join("");
  const innerBody = topError
    ? `<div style="background:#ffe4e4;border:1px solid #ff6b5b;border-radius:10px;padding:14px;color:#b22525;">⚠ Failed to fetch RSS: ${escapeHtml(topError)}</div>`
    : (cards || `<div style="background:#fff4c2;border:1px solid #f0e8d8;border-radius:10px;padding:12px;color:#8a6d00;">RSS feed had no parseable items.</div>`);
  return `
    <section style="margin-bottom:24px;">
      <header style="background:#fff;border:1px solid #e2dccc;border-radius:14px;padding:14px 18px;margin-bottom:14px;">
        <h2 style="font-family:Georgia,serif;font-size:20px;margin:0 0 6px;">
          ${escapeHtml(source.name)}
          <span style="display:inline-block;padding:2px 10px;border-radius:999px;font-size:11px;font-weight:800;background:#fff4c2;color:#8a6d00;margin-left:6px;">${escapeHtml(source.category)}</span>
        </h2>
        <div style="font-size:12px;color:#6b5c80;">
          RSS: <a href="${escapeHtml(source.rss_url)}" target="_blank" rel="noopener" style="color:#1f5fd1;">${escapeHtml(source.rss_url)}</a><br>
          Generated: ${escapeHtml(generatedAt)} · ${articles.length} article${articles.length === 1 ? "" : "s"}
        </div>
        ${summaryBlurb}
      </header>
      ${innerBody}
    </section>
  `;
}

function wrapInDoc(title: string, bodyHtml: string): string {
  return `<!doctype html>
<html><head><meta charset="utf-8"><title>${title}</title>
<style>
  body { margin:0; padding:24px; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#fff9ef; color:#1b1230; }
</style></head>
<body>${bodyHtml}</body></html>`;
}

// ── Per-source verification ────────────────────────────────────────
// Returns ONE source's HTML BLOCK (header + 3 cards) as a fragment —
// not a whole document. The category renderer wraps multiple of these.
// withBody=true → also extract the article body + word count from each
// article HTML. Single-source verify (id:N + url:<RSS>) sets this so
// the editor sees the body word count as a quality signal. Category
// verify leaves it off — fanning out body extraction across ~27
// articles is heavy and the editor doesn't need the per-article detail
// when scanning a whole category.
async function verifyOneFragment(source: any, opts: { withBody?: boolean; stampVerified?: boolean } = {}): Promise<string> {
  const generatedAt = new Date().toISOString();
  let articles: any[] = [];
  let topError: string | null = null;
  try {
    const xml = await fetchTextWithTimeout(source.rss_url, 8000);
    const items = parseFeed(xml, 3);
    articles = await Promise.all(items.map(async (it: any) => {
      try {
        if (!it.link) return { ...it, og: { image: "", title: "", description: "", siteName: "" } };
        const html = await fetchTextWithTimeout(it.link, 8000);
        const result: any = { ...it, feedDescription: it.description, og: extractOg(html) };
        if (opts.withBody) result.body = await extractArticleBody(html);
        return result;
      } catch (e) {
        return { ...it, feedDescription: it.description, og: { image: "", title: "", description: "", siteName: "" }, error: String((e as Error).message || e) };
      }
    }));
  } catch (e) {
    topError = String((e as Error).message || e);
  }
  // Stamp last_verified_at on success (any RSS articles came back) —
  // but only when this is a saved source (id > 0); ad-hoc previews
  // pass stampVerified=false so we never write a row that doesn't exist.
  if (!topError && opts.stampVerified !== false && typeof source.id === "number" && source.id > 0) {
    await sb.from("redesign_source_configs").update({ last_verified_at: generatedAt }).eq("id", source.id);
  }
  return renderSourceBlock(source, generatedAt, articles, topError);
}

async function verifyOneFull(source: any): Promise<string> {
  // Single-source verify gets the heavy treatment: body extraction +
  // word-count summary so the editor can judge feed quality.
  const fragment = await verifyOneFragment(source, { withBody: true, stampVerified: true });
  return wrapInDoc(`Verify · ${escapeHtml(source.name)}`, fragment);
}

async function verifyCategory(category: string): Promise<string> {
  const { data: sources, error } = await sb.from("redesign_source_configs")
    .select("id, name, category, rss_url, enabled, is_backup")
    .eq("category", category)
    .eq("enabled", true)
    .order("priority", { ascending: true });
  if (error) throw error;
  if (!sources || !sources.length) {
    return wrapInDoc(`Verify · ${escapeHtml(category)} · 0 sources`,
      `<div style="background:#fff4c2;border:1px solid #f0e8d8;border-radius:10px;padding:14px;color:#8a6d00;">No enabled sources in this category.</div>`);
  }
  // Fan out across sources. Each verifyOneFragment fans out 3 article
  // fetches internally — 9 sources × (1 RSS + 3 article fetches) = ~36
  // concurrent fetches at peak. Edge runtime handles that fine.
  // withBody is OFF here — body extraction × 27 articles would be heavy
  // and the editor doesn't need that level of detail for a category sweep.
  const fragments = await Promise.all(sources.map((s: any) => verifyOneFragment(s, { withBody: false, stampVerified: true })));
  const joined = fragments.join("\n");
  const header = `<div style="background:#1b1230;color:#ffc83d;padding:14px 20px;border-radius:14px;margin-bottom:20px;">
    <div style="font-family:Georgia,serif;font-size:22px;font-weight:900;">${escapeHtml(category)} category</div>
    <div style="font-size:12px;opacity:.85;">${sources.length} enabled source${sources.length === 1 ? "" : "s"} · generated ${escapeHtml(new Date().toISOString())}</div>
  </div>`;
  return wrapInDoc(`Verify · ${escapeHtml(category)} · ${sources.length} sources`, header + joined);
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  try {
    if (req.method !== "POST") {
      return new Response(JSON.stringify({ error: "POST only" }), {
        status: 405, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    await requireAdmin(req);
    const body = await req.json();
    const target: string = String(body.target || "").trim();

    // id:N — single source, ~5s
    const idMatch = target.match(/^id:(\d+)$/);
    if (idMatch) {
      const sid = Number(idMatch[1]);
      const { data: source, error } = await sb.from("redesign_source_configs")
        .select("id, name, category, rss_url, enabled")
        .eq("id", sid).maybeSingle();
      if (error) throw error;
      if (!source) {
        return new Response(JSON.stringify({ error: `source id ${sid} not found` }), {
          status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      const html = await verifyOneFull(source);
      return new Response(JSON.stringify({
        ok: true, target,
        source: { id: source.id, name: source.name, category: source.category },
        html, generatedAt: new Date().toISOString(),
      }), { headers: { ...corsHeaders, "Content-Type": "application/json" } });
    }

    // category:NAME — fan out across all enabled sources in that category, ~10-15s
    const catMatch = target.match(/^category:([A-Za-z][A-Za-z0-9 _-]*)$/);
    if (catMatch) {
      const cat = catMatch[1];
      const html = await verifyCategory(cat);
      return new Response(JSON.stringify({
        ok: true, target,
        category: cat,
        html, generatedAt: new Date().toISOString(),
      }), { headers: { ...corsHeaders, "Content-Type": "application/json" } });
    }

    // url:<RSS_URL> — ad-hoc preview before adding a new source. Doesn't
    // touch the DB at all — no row created, no last_verified_at stamped.
    // Used by the admin's "Preview" button so an editor can confirm a
    // feed parses + serves real og:images before committing it.
    if (target.startsWith("url:")) {
      const rss = target.slice(4);
      try {
        new URL(rss); // throws on garbage
      } catch {
        return new Response(JSON.stringify({ error: "url: target must be a valid http(s) URL" }), {
          status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      // Synthetic source so renderSourceBlock + verifyOneFragment work
      // unchanged. Skip the last_verified_at stamp since there's no row.
      const adhoc = { id: -1, name: body.name || "(preview)", category: body.category || "—", rss_url: rss };
      // Reuse verifyOneFragment with body extraction — same quality
      // signals as a saved-source verify, just without writing to DB
      // (stampVerified=false keeps it ad-hoc).
      const fragment = await verifyOneFragment(adhoc, { withBody: true, stampVerified: false });
      const html = wrapInDoc(`Preview · ${escapeHtml(adhoc.name)}`, fragment);
      return new Response(JSON.stringify({
        ok: true, target, html, generatedAt: new Date().toISOString(),
      }), { headers: { ...corsHeaders, "Content-Type": "application/json" } });
    }

    return new Response(JSON.stringify({
      error: "Invalid target. Use id:N (saved source), category:NAME (saved sources in a category), or url:<rss> (ad-hoc preview).",
    }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: String((e as Error).message || e) }), {
      status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
