// Verify-source dispatcher for the kidsnews admin page.
//
// Two actions over one POST endpoint:
//
//   POST { action: "dispatch", target: "id:7" | "category:News" | "all" }
//     → Dispatches the news-v2 verify-source.yml workflow with the
//       given target + upload=true. Polls /actions/runs to find the
//       run that just started and returns { run_id, html_url }.
//
//   POST { action: "status", run_id: 12345 }
//     → Reads the run's status. If completed, lists the most recent
//       verify/<ts>/ folder in Supabase Storage and returns the
//       per-target HTML preview public URL.
//
// Auth model: caller must be an authenticated user listed in
// public.redesign_admin_users (same gate the admin page itself uses).
// GitHub PAT lives in public.secrets.GH_PAT (Actions: Read and write
// on daijiong1977/news-v2). CORS is open so the admin page can hit it.

// deno-lint-ignore-file no-explicit-any
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const GH_REPO      = Deno.env.get("GH_REPO") ?? "daijiong1977/news-v2";
const WF_FILENAME  = "verify-source.yml";

const sb = createClient(SUPABASE_URL, SERVICE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

async function readGhPat(): Promise<string> {
  const { data, error } = await sb.rpc("get_secret", { secret_name: "GH_PAT" });
  if (error) throw new Error("get_secret failed: " + error.message);
  if (!data) throw new Error("GH_PAT not configured in public.secrets");
  return String(data);
}

// Authentication: caller must be an admin. We verify via the auth header
// the browser passes (the supabase-js client attaches it automatically).
async function requireAdmin(req: Request): Promise<string> {
  const auth = req.headers.get("authorization") || "";
  if (!auth.startsWith("Bearer ")) throw new Error("Sign-in required");
  const token = auth.slice("Bearer ".length);
  // Use a request-scoped client so RLS sees the user's JWT.
  const ub = createClient(SUPABASE_URL, Deno.env.get("SUPABASE_ANON_KEY") ?? "", {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { headers: { Authorization: `Bearer ${token}` } },
  });
  const { data: { user }, error } = await ub.auth.getUser(token);
  if (error || !user || !user.email) throw new Error("Auth failed");
  // Use service-role client (sb) to read admin allowlist regardless of RLS shape.
  const { data: row } = await sb.from("redesign_admin_users").select("email").eq("email", user.email).maybeSingle();
  if (!row) throw new Error("Not an admin");
  return user.email;
}

async function ghDispatch(target: string): Promise<{ stamped_at: string }> {
  const pat = await readGhPat();
  const url = `https://api.github.com/repos/${GH_REPO}/actions/workflows/${WF_FILENAME}/dispatches`;
  const stampedAt = new Date().toISOString();
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${pat}`,
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({
      ref: "main",
      inputs: { target, upload: "true" },
    }),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`GH dispatch failed (${res.status}): ${t}`);
  }
  return { stamped_at: stampedAt };
}

async function findNewestRun(stampedAt: string): Promise<any> {
  const pat = await readGhPat();
  // The dispatch returns 204 with no body, so we have to look up the run.
  // Poll up to ~10 attempts spaced 1s.
  for (let i = 0; i < 10; i++) {
    await new Promise(r => setTimeout(r, 1000));
    const url = `https://api.github.com/repos/${GH_REPO}/actions/workflows/${WF_FILENAME}/runs?event=workflow_dispatch&per_page=5`;
    const res = await fetch(url, {
      headers: {
        "Accept": "application/vnd.github+json",
        "Authorization": `Bearer ${pat}`,
        "X-GitHub-Api-Version": "2022-11-28",
      },
    });
    if (!res.ok) continue;
    const data = await res.json();
    const runs = data.workflow_runs || [];
    // Find the first run created at or after stamped_at.
    const stampMs = Date.parse(stampedAt);
    const match = runs.find((r: any) => Date.parse(r.created_at) >= stampMs - 2000);
    if (match) return match;
  }
  throw new Error("Couldn't find the new run after 10s of polling");
}

async function getRunStatus(runId: number): Promise<any> {
  const pat = await readGhPat();
  const url = `https://api.github.com/repos/${GH_REPO}/actions/runs/${runId}`;
  const res = await fetch(url, {
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${pat}`,
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  if (!res.ok) throw new Error(`status fetch failed (${res.status})`);
  return res.json();
}

// After completion, find the verify/<ts>/ folder in Supabase Storage
// that matches this run. We list folders inside `verify/` and pick the
// one with mtime closest to (after) the run's started_at.
async function findHtmlPreview(runStartedAt: string, target: string): Promise<string | null> {
  // List "verify/" prefix in redesign-daily-content.
  const { data: tsFolders, error } = await sb.storage.from("redesign-daily-content").list("verify", {
    limit: 50,
    sortBy: { column: "created_at", order: "desc" },
  });
  if (error || !tsFolders) return null;
  const startedMs = Date.parse(runStartedAt);
  // Folder name format: YYYYMMDD-HHMMSS (UTC).
  const fmt = (n: number) => String(n).padStart(2, "0");
  const folderTime = (name: string) => {
    const m = name.match(/^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})$/);
    if (!m) return null;
    return Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
  };
  const candidate = tsFolders
    .map(f => ({ name: f.name, t: folderTime(f.name) }))
    .filter(f => f.t !== null && f.t >= startedMs - 60_000) // within 1m
    .sort((a, b) => (a.t! - b.t!))[0];
  if (!candidate) return null;
  // List files inside that folder and pick the first .html.
  const { data: files } = await sb.storage.from("redesign-daily-content").list(`verify/${candidate.name}`, {
    limit: 50,
    sortBy: { column: "created_at", order: "asc" },
  });
  if (!files || !files.length) return null;
  // Pick the file matching the source if target=id:N, else first html.
  let chosen = files.find(f => f.name.endsWith(".html"));
  if (target.startsWith("id:")) {
    const sid = target.slice(3);
    const m = files.find(f => f.name.includes(`source_${sid}_`) || f.name.includes(`-${sid}-`));
    if (m) chosen = m;
  }
  if (!chosen) return null;
  return `${SUPABASE_URL}/storage/v1/object/public/redesign-daily-content/verify/${candidate.name}/${chosen.name}`;
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
    const action = body.action;
    if (action === "dispatch") {
      const target = String(body.target || "").trim();
      if (!/^(all|category:[A-Za-z]+|id:\d+)$/.test(target)) {
        return new Response(JSON.stringify({ error: "Invalid target" }), {
          status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      const { stamped_at } = await ghDispatch(target);
      const run = await findNewestRun(stamped_at);
      return new Response(JSON.stringify({
        run_id: run.id, html_url: run.html_url, status: run.status,
        started_at: run.created_at, target,
      }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    if (action === "status") {
      const runId = Number(body.run_id);
      if (!Number.isFinite(runId)) {
        return new Response(JSON.stringify({ error: "run_id required" }), {
          status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      const run = await getRunStatus(runId);
      let html_preview_url: string | null = null;
      if (run.status === "completed" && run.conclusion === "success") {
        html_preview_url = await findHtmlPreview(run.created_at, body.target || "all");
      }
      return new Response(JSON.stringify({
        run_id: runId,
        status: run.status,                 // queued | in_progress | completed
        conclusion: run.conclusion,         // success | failure | null
        started_at: run.created_at,
        updated_at: run.updated_at,
        html_url: run.html_url,
        html_preview_url,
      }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    return new Response(JSON.stringify({ error: "Unknown action" }), {
      status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: String((e as Error).message || e) }), {
      status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
