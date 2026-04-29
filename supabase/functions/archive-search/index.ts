// Archive search — full-text search across published articles.
//
// Usage: GET /functions/v1/archive-search?q=<query>&limit=10&category=News
//
// Backed by `redesign_search_index` (one row per story+level, with a
// tsvector `doc_tsv` column kept in sync by trigger). The function
// runs `websearch_to_tsquery` (so quotes / OR / -term work) and
// returns top-N rows ordered by date DESC, then by ts_rank DESC.
//
// Anonymous calls allowed — search results are public catalog data,
// nothing user-specific. Service-role key is kept server-side.

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
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "authorization, content-type, apikey",
};

Deno.serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: CORS_HEADERS });
  }

  const url = new URL(req.url);
  const q = (url.searchParams.get("q") || "").trim();
  const limit = Math.max(1, Math.min(50, parseInt(url.searchParams.get("limit") || "10", 10)));
  const category = (url.searchParams.get("category") || "").trim();
  const level = (url.searchParams.get("level") || "").trim(); // optional

  if (!q) {
    return new Response(JSON.stringify({ error: "missing 'q'" }), {
      status: 400,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  // Use websearch_to_tsquery via .rpc — but PostgREST doesn't expose
  // arbitrary SQL. Easiest path: call a postgres function we define
  // for this. The migration adds `redesign_archive_search()`.
  const { data, error } = await sb.rpc("redesign_archive_search", {
    q,
    p_limit: limit,
    p_category: category || null,
    p_level: level || null,
  });

  if (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  // Dedupe by story_id (return the highest-rank level per story so the
  // UI shows one card per article). Preserve date-DESC order.
  const seen = new Set<string>();
  const deduped: any[] = [];
  for (const r of (data || [])) {
    if (seen.has(r.story_id)) continue;
    seen.add(r.story_id);
    deduped.push(r);
  }

  return new Response(JSON.stringify({
    query: q,
    count: deduped.length,
    results: deduped,
  }), {
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
});
