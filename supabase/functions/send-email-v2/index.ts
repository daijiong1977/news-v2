// send-email-v2 — internal SMTP relay (Gmail). HARDENED 2026-07-08.
//
// This function was an OPEN RELAY: verify_jwt=false with no auth, so anyone
// could POST {to_email, subject, html, from_name} and send arbitrary mail
// from the project's Gmail (spoofable sender name) to any recipient.
//
// It is now INTERNAL-ONLY: callers must present the shared secret in the
// `x-internal-secret` header (checked in constant-ish time against
// SEND_EMAIL_SECRET). Legitimate callers are all server-side:
//   · request-magic-link (kid sign-in)         · send-recovery-code
//   · send-parent-digest                         · send-digest
//   · quality_digest.py                          · pipeline-watchdog.yml
// The browser no longer calls this directly.
//
// ROLLOUT NOTE: deploy this LAST (after every caller passes the secret) — see
// docs/superpowers/specs/2026-07-08-email-security-hardening.md. Deploying it
// before the callers are updated would break outbound email.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { SMTPClient } from "https://deno.land/x/denomailer@1.6.0/mod.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-internal-secret",
};

const SEND_EMAIL_SECRET = Deno.env.get("SEND_EMAIL_SECRET") || "";

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length || a.length === 0) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function htmlToText(html: string): string {
  return html
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|h[1-6]|li|tr|td|th)>/gi, "\n")
    .replace(/<a[^>]*href="([^"]+)"[^>]*>([^<]+)<\/a>/gi, "$2 ($1)")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  try {
    // ── AUTH GATE (new) ──
    if (!SEND_EMAIL_SECRET) {
      return new Response(JSON.stringify({ error: "relay not configured" }), {
        status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    if (!timingSafeEqual(req.headers.get("x-internal-secret") || "", SEND_EMAIL_SECRET)) {
      return new Response(JSON.stringify({ error: "forbidden" }), {
        status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const { to_email, subject, message, html, from_name } = await req.json();
    if (!to_email || !subject || (!message && !html)) {
      return new Response(JSON.stringify({ error: "Missing: to_email, subject, message/html" }), {
        status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    const sc = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    const { data: gmailAddr } = await sc.rpc("get_secret", { secret_name: "GMAIL_ADDRESS" });
    const { data: gmailPass } = await sc.rpc("get_secret", { secret_name: "GMAIL_APP_PASSWORD" });
    if (!gmailAddr || !gmailPass) {
      return new Response(JSON.stringify({ error: "Gmail not configured" }), {
        status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    const senderName = from_name || "kidsnews";
    const client = new SMTPClient({
      connection: { hostname: "smtp.gmail.com", port: 465, tls: true, auth: { username: gmailAddr, password: gmailPass } },
    });
    const textContent = message || (html ? htmlToText(html) : "");
    await client.send({ from: `${senderName} <${gmailAddr}>`, to: to_email, subject, content: textContent, html: html || undefined });
    await client.close();
    return new Response(JSON.stringify({ success: true, message: `Email sent to ${to_email}`, from: senderName }), {
      status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (e) {
    console.error("Send email error:", e);
    return new Response(JSON.stringify({ error: (e as Error).message }), {
      status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
