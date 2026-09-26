// request-magic-link — server-side magic-link sign-in email.
//
// WHY THIS EXISTS (security):
//   The client used to (a) call issue_magic_link and receive the RAW token
//   in the browser, then (b) POST arbitrary {to_email, subject, html,
//   from_name} to the OPEN relay send-email-v2. That let anyone mint+consume
//   a link for any email (token handed to any anon caller) AND send arbitrary
//   mail from the project's Gmail (spoofable from_name).
//
//   This function moves BOTH server-side: it issues the token (never returns
//   it), composes the email itself, and forwards to send-email-v2 WITH the
//   shared secret. The browser only sends {email, client_id} and never sees a
//   token or controls the email body/sender.
//
// It stays verify_jwt=false (kids aren't authenticated), but the abuse
// surface is limited to "send a sign-in link to the given address", and
// issue_magic_link already caps 5 active links per email.
//
// Bug: docs/superpowers/specs/2026-07-08-email-security-hardening.md

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY =
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || Deno.env.get("SUPABASE_SERVICE_KEY")!;
const SEND_EMAIL_SECRET = Deno.env.get("SEND_EMAIL_SECRET") || "";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });
}

const sb = createClient(SUPABASE_URL, SERVICE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

function signinEmailHtml(link: string): string {
  return (
    '<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#fff9ef;padding:24px;color:#1b1230;">' +
    '<h2 style="font-family:Georgia,serif;margin:0 0 12px;font-weight:900;">Sign in to kidsnews</h2>' +
    '<p style="font-size:14px;color:#3a2a4a;line-height:1.5;">' +
    "Tap the button below to sync your reading streak to this email. After this, you can come back from any browser.</p>" +
    '<div style="margin:18px 0;"><a href="' + link + '" ' +
    'style="display:inline-block;background:#1b1230;color:#ffc83d;font-family:Nunito,sans-serif;font-weight:900;' +
    'font-size:15px;padding:14px 22px;border-radius:14px;text-decoration:none;border:2px solid #1b1230;">' +
    "✨ Sync this email to kidsnews</a></div>" +
    '<p style="font-size:12px;color:#9a8d7a;line-height:1.5;">' +
    "This link is single-use and expires in 30 minutes. If you didn't ask for this, ignore this email.</p></div>"
  );
}

Deno.serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json(405, { error: "POST only" });

  if (!SEND_EMAIL_SECRET) {
    return json(500, { error: "SEND_EMAIL_SECRET not configured" });
  }

  let email = "";
  let clientId: string | null = null;
  try {
    const body = await req.json();
    email = String(body.email || "").trim().toLowerCase();
    clientId = body.client_id ? String(body.client_id) : null;
  } catch {
    return json(400, { error: "Invalid JSON body" });
  }
  if (!email || email.indexOf("@") < 1 || email.length > 320) {
    return json(400, { error: "Please enter a valid email." });
  }

  // 1. Issue the token server-side (bound to the REQUESTING device). The
  //    token is NEVER returned to the caller.
  const { data: token, error: issueErr } = await sb.rpc("issue_magic_link", {
    p_email: email,
    p_client_id: clientId,
  });
  if (issueErr || !token) {
    // issue_magic_link raises "Too many pending links..." past 5 active.
    const msg = issueErr?.message || "Could not create a sign-in link.";
    const status = /too many/i.test(msg) ? 429 : 500;
    return json(status, { error: msg });
  }

  // 2. Compose the sign-in email server-side and send via the (now
  //    secret-gated) relay. The origin comes from the request so the link
  //    points back at the site the user is on.
  const origin = req.headers.get("origin") || "https://kidsnews.21mins.com";
  const link = `${origin}/?magic=${encodeURIComponent(String(token))}`;
  const html = signinEmailHtml(link);
  const text =
    "Sign in to kidsnews\n\nTap to sync this email to your reading streak:\n" +
    link + "\n\n(Single-use, expires in 30 minutes. Ignore if you didn't ask for this.)";

  const relay = await fetch(`${SUPABASE_URL}/functions/v1/send-email-v2`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-internal-secret": SEND_EMAIL_SECRET },
    body: JSON.stringify({
      to_email: email,
      subject: "Your kidsnews sign-in link",
      html,
      message: text,
      from_name: "kidsnews",
    }),
  });
  if (!relay.ok) {
    const detail = await relay.text().catch(() => "");
    console.error("send-email-v2 failed:", relay.status, detail.slice(0, 200));
    return json(502, { error: "Could not send the sign-in email. Try again shortly." });
  }

  // Success — no token, no internal detail leaks to the browser.
  return json(200, { success: true });
});
