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
const PR_ACTIONS    = new Set(["merge", "close", "leave", "rollback", "keep"]);
const FEEDBACK_ACTIONS = new Set(["treat-as-bug", "dismiss"]);
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

// ── Feedback row actions ──────────────────────────────────────────
// Buttons in the daily quality-digest email's "feedback awaiting your
// call" section. Two actions per row:
//   ?fb=<row_id>&action=treat-as-bug&sig=<hmac16("feedback|<row_id>|treat-as-bug")>
//     → flip redesign_feedback.triaged_status='converted'
//     → if the row has a github_issue_number, also enqueue it in
//       redesign_autofix_queue so the next 3am/10am scheduled-task fire
//       picks it up. Idempotent like handleIssueAction(fix).
//   ?fb=<row_id>&action=dismiss&sig=<hmac16(...)>
//     → flip redesign_feedback.triaged_status='dismissed'
//     → write a triaged_note recording the email-button origin.
async function handleFeedbackAction(rowId: number, action: string): Promise<Response> {
  // Pull the row first so we know its gh_issue_number + classification.
  const { data: row, error: selErr } = await sb
    .from("redesign_feedback")
    .select("id,gh_issue_number,triaged_status,triage_classification,triage_summary")
    .eq("id", rowId)
    .maybeSingle();
  if (selErr) {
    return html(500, htmlPage({
      title: "DB error", message: `Couldn't load feedback row: ${selErr.message}`,
    }));
  }
  if (!row) {
    return html(404, htmlPage({
      title: "Not found", message: `Feedback row #${rowId} doesn't exist.`,
    }));
  }
  // Idempotent: if already actioned, return a friendly already-done page.
  if (row.triaged_status !== "new") {
    return html(200, htmlPage({
      title: "Already actioned",
      message: `Feedback #${rowId} is already ${row.triaged_status}. No change.`,
    }));
  }

  if (action === "treat-as-bug") {
    // Step 1: flip the feedback row to 'converted'.
    const { error: updErr } = await sb
      .from("redesign_feedback")
      .update({
        triaged_status: "converted",
        triaged_note: `Converted to bug via digest-email button at ${new Date().toISOString()}`,
      })
      .eq("id", rowId);
    if (updErr) {
      return html(500, htmlPage({
        title: "Update failed", message: updErr.message,
      }));
    }

    // Step 2: if there's a GH issue, enqueue it for the scheduled-task fire.
    // No-op when gh_issue_number is null (rare — triage usually opens one).
    if (row.gh_issue_number) {
      const issueNum = row.gh_issue_number;
      // Idempotent: skip if a fix-requested row already exists for this issue.
      const { data: existing } = await sb
        .from("redesign_autofix_queue")
        .select("id,status")
        .eq("github_issue_number", issueNum)
        .in("status", ["queued", "fix-requested", "running"])
        .maybeSingle();
      if (!existing) {
        const { error: insErr } = await sb
          .from("redesign_autofix_queue").insert({
            github_issue_number: issueNum,
            problem_type:        "github_issue",
            status:              "fix-requested",
            problem_detail:      {
              issue_url: `https://github.com/${GH_REPO}/issues/${issueNum}`,
              source: `feedback#${rowId}`,
              summary: row.triage_summary || null,
            },
          });
        if (insErr) {
          return html(500, htmlPage({
            title: "Queue insert failed",
            message: `Feedback row updated, but autofix queue insert failed: ${insErr.message}`,
            color: COLOR.dismiss,
          }));
        }
      }
      return html(200, htmlPage({
        title: "Treated as bug",
        message: `Feedback #${rowId} → converted. GH issue #${issueNum} queued for the next 3am or 10am scheduled-task fire.`,
        detail: "The local Claude Code scheduled task will run kidsnews-bugfix on this issue and open a PR with Closes #" + issueNum + ".",
        color: COLOR.fix,
      }));
    }

    // No GH issue (unusual for triaged rows). Just record the conversion.
    return html(200, htmlPage({
      title: "Converted",
      message: `Feedback #${rowId} marked as converted, but no GH issue exists to queue. Open admin → Feedback to add manually.`,
      color: COLOR.fix,
    }));
  }

  if (action === "dismiss") {
    const { error: updErr } = await sb
      .from("redesign_feedback")
      .update({
        triaged_status: "dismissed",
        triaged_note: `Dismissed via digest-email button at ${new Date().toISOString()}`,
      })
      .eq("id", rowId);
    if (updErr) {
      return html(500, htmlPage({
        title: "Update failed", message: updErr.message,
      }));
    }
    return html(200, htmlPage({
      title: "Dismissed",
      message: `Feedback #${rowId} → dismissed. Won't show in future digests.`,
      color: COLOR.dismiss,
    }));
  }

  return html(400, htmlPage({
    title: "Bad request", message: `Unknown feedback action ${action}.`,
  }));
}

async function handlePrAction(prNum: number, action: string): Promise<Response> {
  if (!GH_ISSUE_TOKEN) {
    return html(500, htmlPage({
      title: "Misconfigured",
      message: "GH_ISSUE_TOKEN not set in this environment.",
    }));
  }

  // For merge/close, hit GH API directly. For rollback, dispatch a
  // workflow that does git revert + push (edge fn can't run git).
  // 'leave' and 'keep' are no-op confirmations — UI feedback only,
  // no DB or GH change.

  if (action === "merge") {
    const r = await githubApi(`pulls/${prNum}/merge`, "PUT",
      { merge_method: "squash" });
    if (r.status >= 300) {
      return html(r.status, htmlPage({
        title: "Merge failed",
        message: `GitHub API: ${r.body.slice(0, 200)}`,
      }));
    }
    const merged: any = (() => { try { return JSON.parse(r.body); } catch { return {}; } })();
    // Mark the queue row as merged + record sha so rollback can find it.
    await sb.from("redesign_autofix_queue").update({
      pr_state:     "merged",
      pr_merged_at: new Date().toISOString(),
      problem_detail: { merged_sha: merged.sha, ...(merged.message ? { merge_msg: merged.message } : {}) },
    }).eq("pr_number", prNum);
    return html(200, htmlPage({
      title: "Merged",
      message: `PR #${prNum} squashed into main.`,
      detail: `Merge commit ${(merged.sha || "").slice(0, 7)} — Vercel will redeploy in ~1 min.`,
      color: COLOR.resolve,
    }));
  }

  if (action === "close") {
    const r = await githubApi(`pulls/${prNum}`, "PATCH", { state: "closed" });
    if (r.status >= 300) {
      return html(r.status, htmlPage({
        title: "Close failed",
        message: `GitHub API: ${r.body.slice(0, 200)}`,
      }));
    }
    await sb.from("redesign_autofix_queue")
      .update({ pr_state: "closed" }).eq("pr_number", prNum);
    return html(200, htmlPage({
      title: "PR closed",
      message: `PR #${prNum} closed without merge.`,
      detail: "The original GitHub issue stays open — claude can take another shot if you re-Fix it from a future digest.",
      color: COLOR.dismiss,
    }));
  }

  if (action === "leave") {
    return html(200, htmlPage({
      title: "Left for review",
      message: `PR #${prNum} left as-is. Tomorrow's digest will surface it again.`,
      color: "#666",
    }));
  }

  if (action === "rollback") {
    // Fetch the merge commit SHA from the queue row.
    const { data: row } = await sb.from("redesign_autofix_queue")
      .select("problem_detail, pr_state").eq("pr_number", prNum).maybeSingle();
    const sha = row?.problem_detail?.merged_sha;
    if (!sha) {
      return html(400, htmlPage({
        title: "Can't rollback",
        message: `No merge commit recorded for PR #${prNum}.`,
        detail: "This usually means the PR was merged outside this system, or merged before pr_state tracking landed.",
      }));
    }
    // Dispatch the rollback workflow with the SHA.
    const dispatch = await githubApi("actions/workflows/pr-rollback.yml/dispatches", "POST",
      { ref: "main", inputs: { merge_sha: sha, pr_number: String(prNum) } });
    if (dispatch.status >= 300) {
      return html(dispatch.status, htmlPage({
        title: "Rollback dispatch failed",
        message: `GitHub API: ${dispatch.body.slice(0, 200)}`,
      }));
    }
    await sb.from("redesign_autofix_queue")
      .update({ pr_state: "closed" }).eq("pr_number", prNum);
    return html(200, htmlPage({
      title: "Rollback queued",
      message: `Reverting merge ${sha.slice(0, 7)} of PR #${prNum} on main.`,
      detail: "GitHub Actions workflow pr-rollback.yml fires now (~30s). Vercel redeploys ~1 min after.",
      color: "#a02b2b",
    }));
  }

  if (action === "keep") {
    return html(200, htmlPage({
      title: "Looks good",
      message: `PR #${prNum} confirmed kept.`,
      detail: "Won't be offered for rollback again.",
      color: COLOR.resolve,
    }));
  }

  return html(400, htmlPage({
    title: "Bad request", message: `Unknown PR action ${action}.`,
  }));
}

Deno.serve(async (req: Request): Promise<Response> => {
  const url = new URL(req.url);
  const action = (url.searchParams.get("action") ?? "").toLowerCase();
  const sig    = (url.searchParams.get("sig") ?? "").toLowerCase();
  const idStr    = url.searchParams.get("id") ?? "";
  const issueStr = url.searchParams.get("issue") ?? "";
  const prStr    = url.searchParams.get("pr") ?? "";
  const fbStr    = url.searchParams.get("fb") ?? "";

  if (!BUTTON_SECRET) {
    return html(500, htmlPage({
      title: "Misconfigured",
      message: "AUTOFIX_BUTTON_SECRET not set in this environment.",
    }));
  }

  // Feedback branch — HMAC namespace "feedback|<row_id>|<action>".
  if (fbStr) {
    const rowId = parseInt(fbStr, 10);
    if (!Number.isFinite(rowId) || rowId <= 0) {
      return html(400, htmlPage({
        title: "Bad request", message: "Missing or invalid `fb` parameter.",
      }));
    }
    if (!FEEDBACK_ACTIONS.has(action)) {
      return html(400, htmlPage({
        title: "Bad request",
        message: `Unknown feedback action ${action}. Expected: treat-as-bug / dismiss.`,
      }));
    }
    const expectedSig = await hmac16(`feedback|${rowId}|${action}`, BUTTON_SECRET);
    if (!constantTimeEqual(sig, expectedSig)) {
      return html(403, htmlPage({
        title: "Invalid signature",
        message: "The button URL signature didn't validate.",
      }));
    }
    return await handleFeedbackAction(rowId, action);
  }

  // PR branch — own HMAC namespace ("pr|N|action")
  if (prStr) {
    const prNum = parseInt(prStr, 10);
    if (!Number.isFinite(prNum) || prNum <= 0) {
      return html(400, htmlPage({
        title: "Bad request", message: "Missing or invalid `pr` parameter.",
      }));
    }
    if (!PR_ACTIONS.has(action)) {
      return html(400, htmlPage({
        title: "Bad request",
        message: `Unknown PR action ${action}. Expected: merge / close / leave / rollback / keep.`,
      }));
    }
    const expectedSig = await hmac16(`pr|${prNum}|${action}`, BUTTON_SECRET);
    if (!constantTimeEqual(sig, expectedSig)) {
      return html(403, htmlPage({
        title: "Invalid signature",
        message: "The button URL signature didn't validate.",
      }));
    }
    return await handlePrAction(prNum, action);
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
