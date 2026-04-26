// Parent Digest — emails parents with a weekly/daily summary of their
// kid(s)' reading activity.
//
// Triggered by the GitHub Actions cron (.github/workflows/parent-digest.yml)
// or manually via:  supabase functions invoke send-digest --no-verify-jwt
//
// Sends through the existing `send-email-v2` edge function (Gmail SMTP).
// No additional secrets required — `send-email-v2` already has
// GMAIL_ADDRESS / GMAIL_APP_PASSWORD configured in public.secrets.
//
// Optional env override:
//   - PARENT_DASHBOARD_URL  e.g. "https://kidsnews.21mins.com/parent.html"
//                           defaults to that URL.
//
// SECURITY: uses the service-role key to bypass RLS for cross-parent
// aggregation. Treat as an internal cron worker — keep its URL off the
// public web; it's reached by GitHub Actions only.

// deno-lint-ignore-file no-explicit-any
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
// send-email-v2 lives at /functions/v1/send-email-v2 on the SAME project.
const SEND_EMAIL_URL = (SUPABASE_URL || "").replace(/\/$/, "") + "/functions/v1/send-email-v2";
const DASH_URL     = Deno.env.get("PARENT_DASHBOARD_URL") ?? "https://kidsnews.21mins.com/parent.html";

const sb = createClient(SUPABASE_URL, SERVICE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

// CORS — the parent dashboard calls this from the browser via the
// "Send me a copy now" button. send-email-v2 uses the same pattern.
const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// ── Helpers ─────────────────────────────────────────────────────────────

function pct(n: number, d: number) { return d ? Math.round((n / d) * 100) : 0; }

function fmtDate(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "—" : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]!));
}

// Window length per cadence — used for activity filtering AND
// throttling (don't double-send within one window).
function windowDays(cadence: string) {
  return cadence === "daily" ? 1 : cadence === "weekly" ? 7 : 0;
}

function isDue(parent: { digest_cadence: string; digest_last_sent_at: string | null }) {
  if (parent.digest_cadence === "off") return false;
  const days = windowDays(parent.digest_cadence);
  if (!parent.digest_last_sent_at) return true;
  const ageMs = Date.now() - new Date(parent.digest_last_sent_at).getTime();
  // Send a touch under the cadence so weekly drift doesn't slip past the cron.
  return ageMs >= (days * 24 * 60 * 60 * 1000) - (60 * 60 * 1000);
}

// ── Per-parent digest ───────────────────────────────────────────────────

type Parent = { id: string; email: string; name: string | null; digest_cadence: string; digest_last_sent_at: string | null };
type Kid    = { client_id: string; display_name: string | null; level: string | null };

async function buildAndSend(parent: Parent): Promise<{ ok: boolean; reason?: string }> {
  const { data: kids, error: kerr } = await sb
    .from("redesign_kid_profiles")
    .select("client_id, display_name, level")
    .eq("parent_user_id", parent.id);
  if (kerr) return { ok: false, reason: kerr.message };
  if (!kids || kids.length === 0) return { ok: false, reason: "no kids linked" };

  const clientIds = kids.map((k: Kid) => k.client_id);
  const since = new Date(Date.now() - windowDays(parent.digest_cadence) * 24 * 60 * 60 * 1000).toISOString();

  const [{ data: events }, { data: quizzes }, { data: discRows }, { data: reactionRows }] = await Promise.all([
    sb.from("redesign_reading_events").select("*").in("client_id", clientIds).gte("occurred_at", since),
    sb.from("redesign_quiz_attempts").select("*").in("client_id", clientIds).gte("attempted_at", since),
    sb.from("redesign_discussion_responses").select("*").in("client_id", clientIds).gte("updated_at", since),
    sb.from("redesign_article_reactions").select("*").in("client_id", clientIds),
  ]);

  // Group by kid
  const sections: string[] = [];
  for (const kid of kids) {
    const kEvents   = (events ?? []).filter((e: any) => e.client_id === kid.client_id);
    const kQuizzes  = (quizzes ?? []).filter((q: any) => q.client_id === kid.client_id);
    const kDisc     = (discRows ?? []).filter((d: any) => d.client_id === kid.client_id);
    const kReactions = (reactionRows ?? []).filter((r: any) => r.client_id === kid.client_id);

    const minutes = kEvents.reduce((s: number, e: any) => s + (parseFloat(e.minutes_added) || 0), 0);
    const finishCount = kEvents.filter((e: any) => e.step === "finish").length;
    const totalCorrect   = kQuizzes.reduce((s: number, q: any) => s + q.correct, 0);
    const totalQuestions = kQuizzes.reduce((s: number, q: any) => s + q.total, 0);
    const avgPct = pct(totalCorrect, totalQuestions);

    const recentReads = (kEvents.filter((e: any) => e.step === "finish") || [])
      .slice(0, 5).map((e: any) => `<li>${escapeHtml(e.story_id)} · ${escapeHtml(e.category || "")}</li>`).join("");

    const wrongList = (kQuizzes ?? []).flatMap((q: any) => {
      // We don't have question text in the DB — best-effort summary only.
      const wrongCount = q.total - q.correct;
      return wrongCount > 0
        ? [`${escapeHtml(q.story_id)} · missed ${wrongCount}/${q.total}`]
        : [];
    }).slice(0, 5).map(s => `<li>${s}</li>`).join("");

    const finalDrafts = (kDisc ?? []).filter((d: any) => d.saved_final).slice(0, 3).map((d: any) => {
      const last = (d.rounds ?? []).at(-1);
      const text = last ? String(last.userText || "").slice(0, 200) : "";
      return `<li><b>${escapeHtml(d.story_id)}</b><br><i>${escapeHtml(text)}…</i></li>`;
    }).join("");

    sections.push(`
      <h2 style="font-family:'Fraunces',Georgia,serif;color:#1b1230;margin:24px 0 8px;">
        ${escapeHtml(kid.display_name || "Your kid")} ${kid.level ? `· ${escapeHtml(kid.level)}` : ""}
      </h2>
      <table style="width:100%;border-collapse:collapse;margin-bottom:14px;">
        <tr>
          <td style="background:#fff9ef;border:1px solid #f0e8d8;border-radius:8px;padding:12px;text-align:center;width:25%;">
            <div style="font-family:'Fraunces',Georgia,serif;font-size:24px;font-weight:900;color:#1b1230;">${minutes.toFixed(1)}</div>
            <div style="font-size:11px;color:#6b5c80;text-transform:uppercase;">minutes read</div>
          </td>
          <td style="background:#fff9ef;border:1px solid #f0e8d8;border-radius:8px;padding:12px;text-align:center;width:25%;">
            <div style="font-family:'Fraunces',Georgia,serif;font-size:24px;font-weight:900;color:#1b1230;">${finishCount}</div>
            <div style="font-size:11px;color:#6b5c80;text-transform:uppercase;">articles finished</div>
          </td>
          <td style="background:#fff9ef;border:1px solid #f0e8d8;border-radius:8px;padding:12px;text-align:center;width:25%;">
            <div style="font-family:'Fraunces',Georgia,serif;font-size:24px;font-weight:900;color:#1b1230;">${avgPct}%</div>
            <div style="font-size:11px;color:#6b5c80;text-transform:uppercase;">quiz correct</div>
          </td>
          <td style="background:#fff9ef;border:1px solid #f0e8d8;border-radius:8px;padding:12px;text-align:center;width:25%;">
            <div style="font-family:'Fraunces',Georgia,serif;font-size:24px;font-weight:900;color:#1b1230;">${kQuizzes.length}</div>
            <div style="font-size:11px;color:#6b5c80;text-transform:uppercase;">quizzes taken</div>
          </td>
        </tr>
      </table>

      ${recentReads ? `<h3 style="font-family:'Fraunces',Georgia,serif;color:#1b1230;font-size:16px;margin:14px 0 6px;">Recent reads</h3><ul style="font-size:14px;color:#1b1230;line-height:1.6;">${recentReads}</ul>` : ''}
      ${wrongList ? `<h3 style="font-family:'Fraunces',Georgia,serif;color:#1b1230;font-size:16px;margin:14px 0 6px;">Quiz misses</h3><ul style="font-size:14px;color:#1b1230;line-height:1.6;">${wrongList}</ul>` : ''}
      ${finalDrafts ? `<h3 style="font-family:'Fraunces',Georgia,serif;color:#1b1230;font-size:16px;margin:14px 0 6px;">Saved discussion answers</h3><ul style="font-size:14px;color:#1b1230;line-height:1.6;">${finalDrafts}</ul>` : ''}
    `);
  }

  const html = `
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fff9ef;color:#1b1230;padding:24px;max-width:680px;margin:0 auto;">
      <div style="text-align:center;margin-bottom:24px;">
        <div style="font-family:'Fraunces',Georgia,serif;font-size:28px;font-weight:900;">kidsnews</div>
        <div style="font-size:13px;color:#6b5c80;">${parent.digest_cadence === 'daily' ? 'Daily' : 'Weekly'} reading digest</div>
      </div>
      <p style="font-size:15px;line-height:1.6;">Hi ${escapeHtml(parent.name || 'there')},</p>
      <p style="font-size:15px;line-height:1.6;">Here's what's happened on kidsnews ${parent.digest_cadence === 'daily' ? 'in the last day' : 'this week'}:</p>
      ${sections.join('')}
      <p style="margin-top:24px;text-align:center;">
        <a href="${DASH_URL}" style="display:inline-block;background:#1b1230;color:#ffc83d;padding:10px 20px;border-radius:10px;text-decoration:none;font-weight:800;font-size:14px;">Open full dashboard ↗</a>
      </p>
      <p style="margin-top:30px;font-size:11px;color:#9a8d7a;text-align:center;">
        You're getting this because you turned on the ${parent.digest_cadence} digest in your kidsnews parent dashboard.
        <a href="${DASH_URL}" style="color:#9a8d7a;">Change cadence</a>.
      </p>
    </div>
  `;

  const subject = `kidsnews ${parent.digest_cadence === 'daily' ? "today" : "this week"}: ${kids.length} kid${kids.length === 1 ? '' : 's'} update`;

  // Plain-text fallback for clients that won't render HTML.
  const text = `kidsnews ${parent.digest_cadence} digest\n\n` +
    `Hi ${parent.name || 'there'} — open ${DASH_URL} for the full report.`;

  const res = await fetch(SEND_EMAIL_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      to_email: parent.email,
      subject,
      message: text,
      html,
      from_name: "kidsnews parent dashboard",
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    return { ok: false, reason: `send-email-v2 ${res.status}: ${err}` };
  }
  // Stamp last_sent so we don't re-send within the cadence window.
  await sb.from("redesign_parent_users")
    .update({ digest_last_sent_at: new Date().toISOString() })
    .eq("id", parent.id);
  return { ok: true };
}

// ── HTTP entrypoint ─────────────────────────────────────────────────────

Deno.serve(async (req) => {
  // Browser preflight — must return CORS headers and 204 (or 200) before
  // the actual POST is allowed.
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  if (!SUPABASE_URL || !SERVICE_KEY) {
    return new Response(JSON.stringify({ error: "Missing SUPABASE_URL/SERVICE_ROLE_KEY" }), {
      status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  // Accept tuning knobs via query OR JSON body (cron uses body).
  const url = new URL(req.url);
  let qForce = url.searchParams.get("force") === "1";
  let qEmail = url.searchParams.get("email") || "";
  if (req.method === "POST") {
    try {
      const body = await req.json();
      if (body && body.force && (body.force === "1" || body.force === true)) qForce = true;
      if (body && body.email) qEmail = String(body.email);
    } catch { /* no/invalid JSON body — that's fine */ }
  }

  let q = sb.from("redesign_parent_users")
    .select("id, email, name, digest_cadence, digest_last_sent_at")
    .neq("digest_cadence", "off");
  if (qEmail) q = q.eq("email", qEmail);
  const { data: parents, error } = await q;
  if (error) return new Response(JSON.stringify({ error: error.message }), {
    status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
  });

  // ?force=1 bypasses the "is_due" cadence check (e.g. for manual test
  // sends from the dashboard). Cadence='off' is still excluded — never
  // surprise an opted-out parent.
  const due = qForce ? (parents ?? []) : (parents ?? []).filter(isDue);
  const results: { email: string; ok: boolean; reason?: string }[] = [];
  for (const p of due) {
    try {
      const r = await buildAndSend(p);
      results.push({ email: p.email, ...r });
    } catch (e) {
      results.push({ email: p.email, ok: false, reason: String(e) });
    }
  }

  return new Response(JSON.stringify({
    candidates: parents?.length ?? 0,
    due: due.length,
    forced: qForce,
    filtered_by_email: qEmail || null,
    sent: results.filter(r => r.ok).length,
    skipped: results.filter(r => !r.ok).length,
    results,
  }, null, 2), {
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
});
