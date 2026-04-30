// autofix-action — receive a click from a digest-email button and
// either flip a redesign_autofix_queue row's status directly
// (dismiss / resolve) OR mark it for the local Mac daemon to pick up
// (fix → status='fix-requested' + 302 redirect to the kidsnews-autofix://
// custom URL scheme so the local app fires immediately when the user
// is on Mac).
//
// GET /functions/v1/autofix-action?id=<N>&action=fix|dismiss|resolve
//
// SECURITY: anonymous (verify_jwt=false) since the URLs land in the
// owner's private inbox. Anyone with the email can click — that's
// the threat model we accept (digest only goes to self@daijiong.com).
// If the inbox is ever shared or breached, rotate by changing the
// supabase project ref or adding an HMAC token.

// deno-lint-ignore-file no-explicit-any
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")
                  || Deno.env.get("SUPABASE_SERVICE_KEY")!;

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

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, c => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;",
  }[c]!));
}

function htmlPage(opts: {
  title: string;
  message: string;
  detail?: string;
  redirect_to?: string;
  color?: string;
}): string {
  const meta = opts.redirect_to
    ? `<meta http-equiv="refresh" content="0; url=${escapeHtml(opts.redirect_to)}">`
    : "";
  const fallback = opts.redirect_to
    ? `<p style="font-size:12px;color:#888;">If nothing happened: this needs your Mac with KidsnewsAutofix.app installed. The fix request is already saved server-side; run <code>~/myprojects/news-v2/scripts/drain-autofix-queue.sh</code> next time you're on your Mac.</p>`
    : "";
  return `<!doctype html><html><head>
<meta charset="utf-8">
${meta}
<title>${escapeHtml(opts.title)}</title>
</head>
<body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f7f5f0;color:#222;padding:32px;">
  <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:10px;padding:28px;box-shadow:0 2px 8px rgba(0,0,0,0.05);">
    <h1 style="margin:0 0 12px;font-size:20px;color:${opts.color || "#1b1230"};">${escapeHtml(opts.title)}</h1>
    <p style="margin:0 0 14px;font-size:15px;">${escapeHtml(opts.message)}</p>
    ${opts.detail ? `<p style="font-size:12px;color:#666;margin:0 0 12px;">${escapeHtml(opts.detail)}</p>` : ""}
    ${fallback}
    <p style="font-size:11px;color:#aaa;margin-top:24px;">You can close this tab.</p>
  </div>
</body></html>`;
}

Deno.serve(async (req: Request): Promise<Response> => {
  const url = new URL(req.url);
  const idStr  = url.searchParams.get("id") ?? "";
  const action = (url.searchParams.get("action") ?? "").toLowerCase();
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

  // Lookup current row (so the page can show what we acted on).
  const { data: row, error: rowErr } = await sb
    .from("redesign_autofix_queue")
    .select("id,status,story_id,level,problem_type")
    .eq("id", id)
    .maybeSingle();

  if (rowErr || !row) {
    return html(404, htmlPage({
      title: "Not found",
      message: `No autofix queue item #${id}.`,
    }));
  }

  // Guard against double-action: only act on rows that are still
  // queued or fix-requested (i.e. not already terminal).
  if (!["queued", "fix-requested"].includes(row.status)) {
    return html(200, htmlPage({
      title: "Already handled",
      message: `Item #${id} is already ${row.status}.`,
      detail: `${row.story_id} · ${row.level} · ${row.problem_type}`,
    }));
  }

  // Apply the new status.
  const newStatus = STATUS_BY_ACTION[action];
  const patch: Record<string, unknown> = { status: newStatus };
  if (newStatus === "resolved") {
    patch.resolved_at = new Date().toISOString();
  }
  const { error: updErr } = await sb
    .from("redesign_autofix_queue")
    .update(patch)
    .eq("id", id);

  if (updErr) {
    return html(500, htmlPage({
      title: "Update failed",
      message: updErr.message,
    }));
  }

  // For fix: redirect to the local custom URL scheme so the Mac app
  // fires immediately. Status was already updated to fix-requested,
  // so even if the redirect doesn't catch (e.g. on iPhone), the
  // daemon's next tick will pick it up.
  const redirect_to = action === "fix"
    ? `kidsnews-autofix://drain?id=${id}`
    : undefined;

  return html(200, htmlPage({
    title: VERB[action],
    message: `Item #${id} (${row.story_id} · ${row.level} · ${row.problem_type}) → ${newStatus}.`,
    detail: action === "fix"
      ? "Now opening KidsnewsAutofix.app to run the fix on your Mac…"
      : undefined,
    redirect_to,
    color: COLOR[action],
  }));
});

function html(status: number, body: string): Response {
  return new Response(body, {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}
