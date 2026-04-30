// submit-feedback — accept user feedback from the kids news website.
//
// POST /functions/v1/submit-feedback
//
// Body: { category, message, page_url?, client_id?, user_level?,
//         user_language?, screenshot_url?,
//         context?: { view, story_id, title, level, category, tab, ... } }
//
// `context` is opaque JSONB — whatever the calling view writes to
// window.__feedbackContext. Triage formats it into the issue body
// so the maintainer knows which page/story the report is about.
//
// - Anonymous (verify_jwt=false). The site sends the anon key as
//   Bearer just like the other public edge functions.
// - Rate-limited: max 5 submissions per IP per minute. The 6th
//   returns 429 — discourages bot abuse without blocking real users.
// - Stores a sha256(ip) hash for rate-limiting; raw IP is never
//   persisted.
// - Validates category enum + message length. PostgREST CHECK
//   constraints are the second line of defense.
//
// Response: { ok: true, id } | { error }

// deno-lint-ignore-file no-explicit-any
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")
                  || Deno.env.get("SUPABASE_SERVICE_KEY")!;

const sb = createClient(SUPABASE_URL, SERVICE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "authorization, content-type, apikey",
};

const ALLOWED_CATEGORIES = new Set(["bug", "suggestion", "content", "other"]);
const RATE_LIMIT_PER_MINUTE = 5;

async function sha256Hex(input: string): Promise<string> {
  const data = new TextEncoder().encode(input);
  const buf = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, "0"))
    .join("");
}

function clientIp(req: Request): string {
  // Supabase puts the original client IP in x-forwarded-for; first
  // entry is the user's address.
  const xff = req.headers.get("x-forwarded-for") || "";
  return xff.split(",")[0].trim() || "unknown";
}

Deno.serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: CORS_HEADERS });
  }
  if (req.method !== "POST") {
    return json({ error: "POST only" }, 405);
  }

  let body: any;
  try {
    body = await req.json();
  } catch {
    return json({ error: "invalid JSON" }, 400);
  }

  // --- Validate ---
  const category = String(body.category || "").trim();
  const message = String(body.message || "").trim();
  if (!ALLOWED_CATEGORIES.has(category)) {
    return json({ error: "invalid category" }, 400);
  }
  if (message.length < 5 || message.length > 4000) {
    return json({ error: "message must be 5-4000 chars" }, 400);
  }

  // --- Rate limit ---
  const ipHash = await sha256Hex(clientIp(req) + "|kidsnews-feedback-salt");
  const since = new Date(Date.now() - 60 * 1000).toISOString();
  const { count, error: countErr } = await sb
    .from("redesign_feedback")
    .select("id", { count: "exact", head: true })
    .eq("ip_hash", ipHash)
    .gte("created_at", since);
  if (countErr) {
    return json({ error: "rate-limit check failed" }, 500);
  }
  if ((count ?? 0) >= RATE_LIMIT_PER_MINUTE) {
    return json({ error: "too many submissions; try again in a minute" }, 429);
  }

  // --- Insert ---
  const ua = (req.headers.get("user-agent") || "").slice(0, 500);
  // context is opaque JSONB — accept any object up to ~4KB serialised
  // to avoid abuse, otherwise drop it.
  let ctx: any = null;
  if (body.context && typeof body.context === "object") {
    try {
      const s = JSON.stringify(body.context);
      if (s.length <= 4000) ctx = body.context;
    } catch {
      // unserialisable — drop
    }
  }
  const row = {
    client_id:      body.client_id      ? String(body.client_id).slice(0, 100)   : null,
    page_url:       body.page_url       ? String(body.page_url).slice(0, 1000)   : null,
    user_level:     body.user_level     ? String(body.user_level).slice(0, 20)   : null,
    user_language:  body.user_language  ? String(body.user_language).slice(0, 8) : null,
    category,
    message,
    screenshot_url: body.screenshot_url ? String(body.screenshot_url).slice(0, 1000) : null,
    user_agent:     ua,
    ip_hash:        ipHash,
    context:        ctx,
  };

  const { data, error } = await sb
    .from("redesign_feedback")
    .insert(row)
    .select("id")
    .single();

  if (error) {
    return json({ error: error.message }, 500);
  }

  return json({ ok: true, id: data?.id }, 200);
});

function json(payload: any, status: number): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
}
