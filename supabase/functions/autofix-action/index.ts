// autofix-action — receive a click from a digest-email button and
// flip a redesign_autofix_queue row's status. The digest emails three
// buttons per escalated row:
//
//   GET /functions/v1/autofix-action?id=<N>&action=<dismiss|resolve|fix>&sig=<hmac>
//
// SECURITY: HMAC-SHA256 over `id|action` using AUTOFIX_BUTTON_SECRET
// (shared between this fn and pipeline.quality_digest). 16 hex chars
// (64 bits) is sufficient — ids are not secret, the only thing the
// sig prevents is an attacker minting a button URL for a row they
// didn't see in the email. Constant-time compare against forgery.
//
// Action mapping:
//   dismiss → status='dismissed'  (don't try again)
//   resolve → status='resolved'   (manual override; admin says it's fine)
//   fix     → status='fix-requested'  (Mac listener picks up at next tick)
//
// No client redirect — the Mac listener polls every 4h, so we just
// confirm "queued for next Mac tick" and leave it.

// deno-lint-ignore-file no-explicit-any
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")
                  || Deno.env.get("SUPABASE_SERVICE_KEY")!;
const BUTTON_SECRET = Deno.env.get("AUTOFIX_BUTTON_SECRET") || "";

const sb = createClient(SUPABASE_URL, SERVICE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const ACTIONS = new Set(["fix", "dismiss", "resolve"]);
const STATUS_BY_ACTION: Record<string, string> = {
  fix:     "fix-requested",
  dismiss: "dismissed",
  resolve: "resolved",
};
const COLOR: Record<string, string> = {
  fix:     "#1b1230",
  dismiss: "#666",
  resolve: "#197a3b",
};
const VERB: Record<string, string> = {
  fix:     "Fix queued",
  dismiss: "Dismissed",
  resolve: "Marked resolved",
};

async function hmac16(payload: string, secret: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(payload));
  return Array.from(new Uint8Array(sig))
    .map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
}

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, c => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;",
  }[c]!));
}

function htmlPage(opts: {
  title: string; message: string; detail?: string; color?: string;
}): string {
  return `<!doctype html><html><head>
<meta charset="utf-8">
<title>${escapeHtml(opts.title)}</title>
</head>
<body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f7f5f0;color:#222;padding:32px;">
  <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:10px;padding:28px;box-shadow:0 2px 8px rgba(0,0,0,0.05);">
    <h1 style="margin:0 0 12px;font-size:20px;color:${opts.color || "#1b1230"};">${escapeHtml(opts.title)}</h1>
    <p style="margin:0 0 14px;font-size:15px;">${escapeHtml(opts.message)}</p>
    ${opts.detail ? `<p style="font-size:12px;color:#666;margin:0 0 12px;">${escapeHtml(opts.detail)}</p>` : ""}
    <p style="font-size:11px;color:#aaa;margin-top:24px;">You can close this tab.</p>
  </div>
</body></html>`;
}

function html(status: number, body: string): Response {
  return new Response(new TextEncoder().encode(body), {
    status, headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

// ── GitHub issue actions ───────────────────────────────────────────
// Same email-button pattern, but routing to GH actions instead of
// queue rows. Buttons in the feedback-triage email use:
//   ?issue=<N>&action=<fix|close|snooze>&sig=<hmac16("issue|N|action")>
// where:
//   fix     → insert a queue row with problem_type='github_issue',
//             status='fix-requested'. Mac claude -p picks it up at the
//             next 04:00 ET tick, reads the issue body via gh CLI,
//             scopes edits to the page in the issue context block,
//             opens a PR with Closes #N.
//   close   → call GH API to close the issue with reason=not_planned.
//   snooze  → add 'todo:later' label so the next triage email skips it
//             for 7 days. (Triage script filters on label age.)

const ISSUE_ACTIONS = new Set(["fix", "close", "snooze"]);
const GH_ISSUE_TOKEN = Deno.env.get("GH_ISSUE_TOKEN") || "";
const GH_REPO = Deno.env.get("GH_REPO") || "daijiong1977/news-v2";

async function githubApi(path: string, method: string, body?: unknown): Promise<{ status: number; body: string }> {
  const r = await fetch(`https://api.github.com/repos/${GH_REPO}/${path}`, {
    method,
    headers: {
      "Authorization": `Bearer ${GH_ISSUE_TOKEN}`,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  return { status: r.status, body: await r.text() };
}

async function handleIssueAction(issueNum: number, action: string): Promise<Response> {
  if (!GH_ISSUE_TOKEN) {
    return html(500, htmlPage({
      title: "Misconfigured",
      message: "GH_ISSUE_TOKEN not set in this environment.",
    }));
  }

  if (action === "fix") {
    // Insert a queue row pointing at this GH issue.
    // Idempotent: if a fix-requested row already exists for this
    // issue, don't double-queue.
    const { data: existing } = await sb
      .from("redesign_autofix_queue")
      .select("id,status")
      .eq("github_issue_number", issueNum)
      .in("status", ["queued", "fix-requested", "running"])
      .maybeSingle();
    if (existing) {
      return html(200, htmlPage({
        title: "Already queued",
        message: `Issue #${issueNum} is already in the autofix queue (row ${existing.id}, status ${existing.status}).`,
      }));
    }
    const { error: insErr } = await sb
      .from("redesign_autofix_queue").insert({
        github_issue_number: issueNum,
        problem_type:        "github_issue",
        status:              "fix-requested",
        problem_detail:      { issue_url: `https://github.com/${GH_REPO}/issues/${issueNum}` },
      });
    if (insErr) {
      return html(500, htmlPage({
        title: "Insert failed", message: insErr.message,
      }));
    }
    return html(200, htmlPage({
      title: "Queued for Claude",
      message: `Issue #${issueNum} → fix-requested.`,
      detail: "Mac listener will pick it up at the next 04:00 ET tick. claude -p will load the kidsnews-bugfix skill, read the issue, and open a PR with Closes #" + issueNum + ".",
      color: COLOR.fix,
    }));
  }

  if (action === "close") {
    const r = await githubApi(`issues/${issueNum}`, "PATCH",
      { state: "closed", state_reason: "not_planned" });
    if (r.status >= 300) {
      return html(r.status, htmlPage({
        title: "GitHub API error",
        message: `Couldn't close issue #${issueNum}: ${r.body.slice(0, 200)}`,
      }));
    }
    return html(200, htmlPage({
      title: "Closed",
      message: `Issue #${issueNum} → closed (reason: not planned).`,
      color: COLOR.dismiss,
    }));
  }

  if (action === "snooze") {
    // Ensure 'todo:later' label exists, then attach it to the issue.
    // Idempotent: GitHub silently no-ops re-adding an existing label.
    await githubApi("labels", "POST",
      { name: "todo:later", color: "ededed",
        description: "Snoozed by admin via digest-email button — triage skips for 7 days" });
    const r = await githubApi(`issues/${issueNum}/labels`, "POST",
      { labels: ["todo:later"] });
    if (r.status >= 300) {
      return html(r.status, htmlPage({
        title: "GitHub API error",
        message: `Couldn't snooze issue #${issueNum}: ${r.body.slice(0, 200)}`,
      }));
    }
    return html(200, htmlPage({
      title: "Snoozed 7d",
      message: `Issue #${issueNum} → labeled 'todo:later'.`,
      detail: "Next 7 days of triage emails will skip this issue. After that, it'll surface again unless you remove the label.",
      color: "#7a4d18",
    }));
  }

  return html(400, htmlPage({
    title: "Bad request", message: `Unknown issue action ${action}.`,
  }));
}

Deno.serve(async (req: Request): Promise<Response> => {
  const url = new URL(req.url);
  const action = (url.searchParams.get("action") ?? "").toLowerCase();
  const sig    = (url.searchParams.get("sig") ?? "").toLowerCase();
  const idStr    = url.searchParams.get("id") ?? "";
  const issueStr = url.searchParams.get("issue") ?? "";

  if (!BUTTON_SECRET) {
    return html(500, htmlPage({
      title: "Misconfigured",
      message: "AUTOFIX_BUTTON_SECRET not set in this environment.",
    }));
  }

  // Branch on which target was specified. issue= takes precedence —
  // gh issue actions live in their own HMAC namespace ("issue|N|action")
  // so a leaked queue-row sig can't be replayed against an issue.
  if (issueStr) {
    const issueNum = parseInt(issueStr, 10);
    if (!Number.isFinite(issueNum) || issueNum <= 0) {
      return html(400, htmlPage({
        title: "Bad request", message: "Missing or invalid `issue` parameter.",
      }));
    }
    if (!ISSUE_ACTIONS.has(action)) {
      return html(400, htmlPage({
        title: "Bad request",
        message: `Unknown issue action ${action}. Expected: fix / close / snooze.`,
      }));
    }
    const expectedSig = await hmac16(`issue|${issueNum}|${action}`, BUTTON_SECRET);
    if (!constantTimeEqual(sig, expectedSig)) {
      return html(403, htmlPage({
        title: "Invalid signature",
        message: "The button URL signature didn't validate.",
      }));
    }
    return await handleIssueAction(issueNum, action);
  }

  // ── Queue-row action path (existing) ────────────────────────────
  const id = parseInt(idStr, 10);
  if (!Number.isFinite(id) || id <= 0) {
    return html(400, htmlPage({
      title: "Bad request", message: "Missing or invalid `id` parameter.",
    }));
  }
  if (!ACTIONS.has(action)) {
    return html(400, htmlPage({
      title: "Bad request",
      message: `Unknown action ${action}. Expected: fix / dismiss / resolve.`,
    }));
  }
  const expectedSig = await hmac16(`${id}|${action}`, BUTTON_SECRET);
  if (!constantTimeEqual(sig, expectedSig)) {
    return html(403, htmlPage({
      title: "Invalid signature",
      message: "The button URL signature didn't validate. This usually means the URL was edited or the secret was rotated.",
    }));
  }

  const { data: row, error: rowErr } = await sb
    .from("redesign_autofix_queue")
    .select("id,status,story_id,level,problem_type")
    .eq("id", id)
    .maybeSingle();
  if (rowErr || !row) {
    return html(404, htmlPage({
      title: "Not found", message: `No autofix queue item #${id}.`,
    }));
  }

  // Idempotency: only act on non-terminal rows.
  const TERMINAL = new Set(["resolved", "dismissed"]);
  if (TERMINAL.has(row.status)) {
    return html(200, htmlPage({
      title: "Already handled",
      message: `Item #${id} is already ${row.status}.`,
      detail: `${row.story_id} · ${row.level} · ${row.problem_type}`,
    }));
  }
  if (row.status === "fix-requested" && action === "fix") {
    return html(200, htmlPage({
      title: "Already queued",
      message: `Item #${id} is already waiting for the Mac listener.`,
      detail: `${row.story_id} · ${row.level} · ${row.problem_type}`,
    }));
  }

  const newStatus = STATUS_BY_ACTION[action];
  const patch: Record<string, unknown> = { status: newStatus };
  if (newStatus === "resolved") patch.resolved_at = new Date().toISOString();
  const { error: updErr } = await sb
    .from("redesign_autofix_queue").update(patch).eq("id", id);
  if (updErr) {
    return html(500, htmlPage({
      title: "Update failed", message: updErr.message,
    }));
  }

  const detailMsg = action === "fix"
    ? "The Mac listener will drain queued fixes at its next 04:00 ET tick."
    : undefined;
  return html(200, htmlPage({
    title: VERB[action],
    message: `Item #${id} (${row.story_id} · ${row.level} · ${row.problem_type}) → ${newStatus}.`,
    detail: detailMsg,
    color: COLOR[action],
  }));
});
