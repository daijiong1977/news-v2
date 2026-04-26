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
function renderSourceBlock(source: any, generatedAt: string, articles: any[], topError: string | null = null): string {
  const cards = articles.map((a: any, i: number) => `
    <article style="background:#fff;border:1px solid #e2dccc;border-radius:14px;overflow:hidden;margin-bottom:14px;display:grid;grid-template-columns:1fr 2fr;gap:0;">
      ${a.og.image
        ? `<div style="background:url('${escapeHtml(a.og.image)}') center/cover, #f0e8d8; min-height:200px;"></div>`
        : `<div style="background:#f0e8d8;min-height:200px;display:flex;align-items:center;justify-content:center;color:#9a8d7a;font-size:13px;">no og:image</div>`}
      <div style="padding:14px 18px;">
        <div style="font-size:11px;color:#9a8d7a;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;">
          Article ${i + 1}${a.pubDate ? " · " + escapeHtml(a.pubDate) : ""}
        </div>
        <h3 style="font-family:Georgia,serif;font-size:18px;font-weight:900;color:#1b1230;margin:0 0 8px;line-height:1.25;">
          ${escapeHtml(a.og.title || a.title || "(untitled)")}
        </h3>
        <p style="font-size:13.5px;color:#3a2a4a;line-height:1.55;margin:0 0 10px;">
          ${escapeHtml(a.og.description || a.feedDescription || "(no description)").slice(0, 360)}
        </p>
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
async function verifyOneFragment(source: any): Promise<string> {
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
        return { ...it, feedDescription: it.description, og: extractOg(html) };
      } catch (e) {
        return { ...it, feedDescription: it.description, og: { image: "", title: "", description: "", siteName: "" }, error: String((e as Error).message || e) };
      }
    }));
  } catch (e) {
    topError = String((e as Error).message || e);
  }
  // Stamp last_verified_at on success (any RSS articles came back).
  if (!topError) {
    await sb.from("redesign_source_configs").update({ last_verified_at: generatedAt }).eq("id", source.id);
  }
  return renderSourceBlock(source, generatedAt, articles, topError);
}

async function verifyOneFull(source: any): Promise<string> {
  const fragment = await verifyOneFragment(source);
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
  const fragments = await Promise.all(sources.map(s => verifyOneFragment(s)));
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
      const generatedAt = new Date().toISOString();
      let articles: any[] = [];
      let topError: string | null = null;
      try {
        const xml = await fetchTextWithTimeout(rss, 8000);
        const items = parseFeed(xml, 3);
        articles = await Promise.all(items.map(async (it: any) => {
          try {
            if (!it.link) return { ...it, og: { image: "", title: "", description: "", siteName: "" } };
            const html = await fetchTextWithTimeout(it.link, 8000);
            return { ...it, feedDescription: it.description, og: extractOg(html) };
          } catch (e) {
            return { ...it, feedDescription: it.description, og: { image: "", title: "", description: "", siteName: "" }, error: String((e as Error).message || e) };
          }
        }));
      } catch (e) {
        topError = String((e as Error).message || e);
      }
      const fragment = renderSourceBlock(adhoc, generatedAt, articles, topError);
      const html = wrapInDoc(`Preview · ${escapeHtml(adhoc.name)}`, fragment);
      return new Response(JSON.stringify({
        ok: !topError, target,
        articleCount: articles.length,
        hasErrors: articles.some(a => a.error) || !!topError,
        html, generatedAt,
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
