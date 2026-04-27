// trigger-pipeline — admin-gated GitHub workflow dispatch.
//
// Why: prior pattern required logging into a terminal + running
// `gh workflow run daily-pipeline.yml -f pipeline_variant=mega` to
// kick a manual run. Storing a GitHub PAT in the kid app's
// localStorage was a no-go for security; pushing it through this
// edge function keeps the secret server-side.
//
// Auth: caller's JWT must belong to a row in redesign_admin_users
// (same gate verify-source uses).
//
// Env required:
//   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY — set
//     by Supabase automatically.
//   GITHUB_DISPATCH_TOKEN — fine-grained PAT with Actions: read+write
//     on daijiong1977/news-v2. Falls back to KIDSNEWS_DISPATCH_TOKEN
//     (the existing token used by republish-bundle.yml) if the user
//     reuses that PAT — same fine-grained scope works as long as
//     news-v2 is in the PAT's repo allowlist.
//
// Workflows allowlist: only the three that make sense for an admin
// to trigger from the UI. Anything else returns 400.
//
// Returns: { ok, workflow, inputs, dispatchedAt, runId, runUrl, adminEmail }
// runId / runUrl best-effort — GitHub's dispatches endpoint returns
// 204 with no body, so we poll the workflow's recent runs to find
// the one we just created. ~3-9s extra round trip; tolerable for
// "click → watch the GH page" ergonomics.

// deno-lint-ignore-file no-explicit-any
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const ANON_KEY     = Deno.env.get("SUPABASE_ANON_KEY") ?? "";
const GH_TOKEN     = Deno.env.get("GITHUB_DISPATCH_TOKEN")
                   ?? Deno.env.get("KIDSNEWS_DISPATCH_TOKEN")
                   ?? "";

const REPO = "daijiong1977/news-v2";
const ALLOWED_WORKFLOWS: Set<string> = new Set([
  "daily-pipeline.yml",
  "republish-bundle.yml",
  "parent-digest.yml",
]);

const sb = createClient(SUPABASE_URL, SERVICE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const json = (status: number, body: any) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });

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
  const { data: row } = await sb.from("redesign_admin_users")
    .select("email")
    .eq("email", user.email)
    .maybeSingle();
  if (!row) throw new Error("Not an admin");
  return user.email;
}

async function findRecentRun(workflow: string, dispatchedAt: string) {
  // GitHub's dispatch response is 204 with no body, so we have to
  // hit /runs and pick the freshest one created within ~5s of our
  // dispatch. Poll a few times — propagation takes 1-3s typically.
  const url = `https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/runs?per_page=5&event=workflow_dispatch`;
  const dispatchedMs = Date.parse(dispatchedAt) - 5_000; // 5s slack
  for (let i = 0; i < 6; i++) {
    await new Promise((r) => setTimeout(r, 1_500));
    const r = await fetch(url, {
      headers: {
        "Accept": "application/vnd.github+json",
        "Authorization": `Bearer ${GH_TOKEN}`,
        "X-GitHub-Api-Version": "2022-11-28",
      },
    });
    if (!r.ok) continue;
    const data: any = await r.json();
    const candidates = (data.workflow_runs || []) as any[];
    const recent = candidates.find((row) => Date.parse(row.created_at) >= dispatchedMs);
    if (recent) return { runId: recent.id as number, runUrl: recent.html_url as string };
  }
  return { runId: null, runUrl: null };
}

// Status check: GET single run by id. Returns the lightweight summary
// the admin UI cares about (status, conclusion, html_url, durations).
async function getRunStatus(runId: number) {
  const url = `https://api.github.com/repos/${REPO}/actions/runs/${runId}`;
  const r = await fetch(url, {
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${GH_TOKEN}`,
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  if (!r.ok) {
    const errText = await r.text();
    throw new Error(`GitHub run lookup ${r.status}: ${errText.slice(0, 300)}`);
  }
  const data: any = await r.json();
  return {
    runId: data.id,
    status: data.status,            // "queued" | "in_progress" | "completed"
    conclusion: data.conclusion,    // null until completed; then "success"|"failure"|"cancelled"|...
    runUrl: data.html_url,
    name: data.name,
    runStartedAt: data.run_started_at,
    updatedAt: data.updated_at,
  };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  try {
    if (req.method !== "POST") return json(405, { error: "POST only" });
    const adminEmail = await requireAdmin(req);

    const body = await req.json().catch(() => ({}));
    // Two actions: default = "dispatch" (kick a workflow), "status" = look up
    // an existing run. Status check uses the same admin auth + same PAT;
    // separating into its own action keeps the dispatch path lean.
    const action: string = String(body.action || "dispatch");

    if (action === "status") {
      const runId = Number(body.runId);
      if (!Number.isFinite(runId) || runId <= 0) {
        return json(400, { error: "runId required for status action" });
      }
      if (!GH_TOKEN) return json(500, { error: "GITHUB_DISPATCH_TOKEN not configured" });
      try {
        const s = await getRunStatus(runId);
        return json(200, { ok: true, ...s });
      } catch (e) {
        return json(502, { error: String((e as Error).message || e) });
      }
    }

    const workflow: string = String(body.workflow || "daily-pipeline.yml");
    const ref: string = String(body.ref || "main");
    const inputs: Record<string, string> = (body.inputs && typeof body.inputs === "object") ? body.inputs : {};

    if (!ALLOWED_WORKFLOWS.has(workflow)) {
      return json(400, { error: `workflow not allowed: ${workflow}`,
        hint: `Allowed: ${[...ALLOWED_WORKFLOWS].join(", ")}` });
    }
    if (!GH_TOKEN) {
      return json(500, {
        error: "GITHUB_DISPATCH_TOKEN (or KIDSNEWS_DISPATCH_TOKEN) is not configured on the edge function",
        hint: "Set via: supabase secrets set GITHUB_DISPATCH_TOKEN=<fine-grained PAT with Actions:write on daijiong1977/news-v2>",
      });
    }

    const dispatchedAt = new Date().toISOString();
    const dispatchUrl = `https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/dispatches`;
    const ghResp = await fetch(dispatchUrl, {
      method: "POST",
      headers: {
        "Accept": "application/vnd.github+json",
        "Authorization": `Bearer ${GH_TOKEN}`,
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref, inputs }),
    });

    if (ghResp.status !== 204) {
      const errText = await ghResp.text();
      console.warn(`[trigger-pipeline] dispatch ${ghResp.status}:`, errText);
      return json(502, {
        error: `GitHub dispatch failed: ${ghResp.status}`,
        details: errText.slice(0, 500),
        hint: (ghResp.status === 401 || ghResp.status === 403)
          ? "Token is missing or lacks 'Actions: read+write' on daijiong1977/news-v2 — check the fine-grained PAT scope."
          : (ghResp.status === 404)
          ? "Repo or workflow not found — confirm the workflow file is on the default branch (main)."
          : (ghResp.status === 422)
          ? "Inputs were rejected — likely an unknown input key for this workflow."
          : null,
      });
    }

    // Best-effort: find the run we just created so the admin can click through.
    const { runId, runUrl } = await findRecentRun(workflow, dispatchedAt);

    return json(200, {
      ok: true,
      workflow,
      ref,
      inputs,
      dispatchedAt,
      runId,
      runUrl,
      adminEmail,
    });
  } catch (e) {
    return json(500, { error: String((e as Error).message || e) });
  }
});
