// autofix-review — browser control-panel page for the autofix queue.
//
// The daily digest email contains exactly ONE button: "Review pending
// fixes →". That button links here. This function renders an HTML
// page listing every queued / fix-requested item with per-item
// action buttons (Fix / Dismiss / Resolved). Each button posts to
// the existing autofix-action edge function.
//
// Why this exists: an email with N items × 3 buttons = 3N URLs to
// the same supabase.co domain triggers Gmail's bulk-mail spam
// heuristics and the email can be silently dropped (not even spam'd,
// just gone). Keeping the email at one link lets it land in inbox;
// the action buttons live on a webpage where there's no such limit.
//
// GET /functions/v1/autofix-review

// deno-lint-ignore-file no-explicit-any
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")
                  || Deno.env.get("SUPABASE_SERVICE_KEY")!;

const sb = createClient(SUPABASE_URL, SERVICE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, c => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;",
  }[c]!));
}

function actionBtn(id: number, action: "fix" | "dismiss" | "resolve"): string {
  const cfg: Record<string, { label: string; color: string }> = {
    fix:     { label: "🛠️ Fix",     color: "#1b1230" },
    dismiss: { label: "🚫 Dismiss", color: "#666"     },
    resolve: { label: "✓ Resolved",  color: "#197a3b" },
  };
  const c = cfg[action];
  return `<a href="${SUPABASE_URL}/functions/v1/autofix-action?id=${id}&action=${action}"
    style="display:inline-block;padding:7px 14px;margin-right:6px;
           background:#fff;color:${c.color};border:1.5px solid ${c.color};
           border-radius:8px;text-decoration:none;font-size:13px;
           font-weight:700;">${c.label}</a>`;
}

Deno.serve(async (_req: Request): Promise<Response> => {
  // Pull every actionable row.
  const { data: rows, error } = await sb
    .from("redesign_autofix_queue")
    .select("id,published_date,story_id,level,problem_type,problem_detail,attempts,status,created_at")
    .in("status", ["queued", "fix-requested", "running"])
    .order("created_at", { ascending: true })
    .limit(100);

  if (error) {
    return new Response(`<h1>Error</h1><pre>${escapeHtml(error.message)}</pre>`,
      { status: 500, headers: { "Content-Type": "text/html; charset=utf-8" } });
  }

  // Also grab a few recent terminal rows so the user has context for
  // what was already handled today.
  const { data: recent } = await sb
    .from("redesign_autofix_queue")
    .select("id,story_id,level,problem_type,status,resolved_at")
    .in("status", ["resolved", "dismissed", "failed"])
    .order("updated_at", { ascending: false })
    .limit(10);

  const items = rows || [];
  const recentRows = recent || [];

  let body = `<!doctype html><html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Autofix Review</title>
</head>
<body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f7f5f0;color:#222;padding:24px;margin:0;">
  <div style="max-width:780px;margin:0 auto;background:#fff;border-radius:12px;padding:28px;box-shadow:0 2px 8px rgba(0,0,0,0.05);">
    <h1 style="margin:0 0 4px;font-size:22px;color:#1b1230;">🛠️ Autofix Review</h1>
    <div style="font-size:12px;color:#888;margin-bottom:18px;">Queue control panel · last refreshed ${new Date().toISOString()}</div>`;

  if (items.length === 0) {
    body += `
    <div style="padding:28px 16px;background:#ecfaf0;border-radius:8px;
                font-size:15px;color:#197a3b;text-align:center;">
      ✓ Nothing pending. Queue is clean.
    </div>`;
  } else {
    body += `
    <div style="margin-bottom:14px;font-size:14px;color:#7a4d18;">
      <strong>${items.length} item${items.length === 1 ? "" : "s"}</strong> waiting for your action.
    </div>`;

    for (const r of items) {
      const detail = r.problem_detail
        ? `<div style="font-size:11px;color:#666;font-family:Menlo,monospace;margin-top:4px;">${escapeHtml(JSON.stringify(r.problem_detail))}</div>`
        : "";
      const attemptNote = r.attempts > 0
        ? `<span style="color:#a02b2b;font-size:11px;margin-left:8px;">attempted ${r.attempts}x</span>`
        : "";
      const statusBadge = r.status === "fix-requested"
        ? `<span style="display:inline-block;padding:1px 6px;border-radius:4px;background:#fff5e8;color:#7a4d18;font-size:10px;font-weight:700;margin-left:8px;">FIX QUEUED — drain on Mac</span>`
        : r.status === "running"
        ? `<span style="display:inline-block;padding:1px 6px;border-radius:4px;background:#fff1f1;color:#a02b2b;font-size:10px;font-weight:700;margin-left:8px;">RUNNING</span>`
        : "";
      body += `
    <div style="border:1px solid #f0d9b0;background:#fff5e8;border-radius:10px;padding:14px 16px;margin-bottom:12px;">
      <div style="font-weight:700;font-size:14px;color:#1b1230;">
        <code style="font-size:12px;">${escapeHtml(r.story_id)}</code> · ${escapeHtml(r.level)} · ${escapeHtml(r.problem_type)}
        ${attemptNote}${statusBadge}
      </div>
      <div style="font-size:11px;color:#888;margin-top:2px;">
        Submitted ${escapeHtml(r.created_at)} · Item #${r.id}
      </div>
      ${detail}
      <div style="margin-top:10px;">
        ${actionBtn(r.id, "fix")}
        ${actionBtn(r.id, "dismiss")}
        ${actionBtn(r.id, "resolve")}
      </div>
    </div>`;
    }

    body += `
    <div style="margin-top:18px;padding:12px 14px;background:#fafafa;border-radius:8px;font-size:11px;color:#666;line-height:1.5;">
      <strong>Action meanings:</strong><br>
      <strong>🛠️ Fix</strong> — marks for the local Claude Code agent on your Mac to regen this article. The button page will redirect to <code>kidsnews-autofix://drain</code>; on Mac that fires KidsnewsAutofix.app and runs the fix. On iPhone the redirect harmlessly fails — the row is still queued for the next time you're on Mac.<br>
      <strong>🚫 Dismiss</strong> — ignore (won't retry).<br>
      <strong>✓ Resolved</strong> — already-fine elsewhere, mark closed without running.
    </div>`;
  }

  if (recentRows.length > 0) {
    body += `
    <h2 style="font-size:15px;color:#1b1230;margin-top:28px;border-top:1px solid #eee;padding-top:18px;">Recently handled</h2>
    <table style="width:100%;border-collapse:collapse;font-size:11px;color:#666;">
      <thead><tr style="text-align:left;color:#888;">
        <th style="padding:5px 6px;">When</th>
        <th style="padding:5px 6px;">Item</th>
        <th style="padding:5px 6px;">Status</th>
      </tr></thead><tbody>`;
    for (const r of recentRows) {
      body += `
      <tr style="border-top:1px solid #f5f5f5;">
        <td style="padding:5px 6px;font-family:Menlo,monospace;">${r.resolved_at ? r.resolved_at.slice(0,19).replace("T", " ") : "—"}</td>
        <td style="padding:5px 6px;"><code>${escapeHtml(r.story_id)}</code> · ${escapeHtml(r.level)} · ${escapeHtml(r.problem_type)}</td>
        <td style="padding:5px 6px;">${escapeHtml(r.status)}</td>
      </tr>`;
    }
    body += `</tbody></table>`;
  }

  body += `
    <div style="margin-top:24px;font-size:11px;color:#aaa;">
      Bookmark this URL — it's always live, not tied to any specific email.
    </div>
  </div>
</body></html>`;

  return new Response(body, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-cache",
    },
  });
});
