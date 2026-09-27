// Authenticated parent-only recovery email. Neither recipient nor message
// content is accepted from the browser.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const URL = Deno.env.get("SUPABASE_URL") || "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") || "";
const MAIL_SECRET = Deno.env.get("SEND_EMAIL_SECRET") || "";
const db = createClient(URL, SERVICE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});
const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const reply = (status: number, body: unknown) => new Response(JSON.stringify(body), {
  status, headers: { ...cors, "Content-Type": "application/json" },
});
const escapeHtml = (value: string) => value.replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] || c);

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return reply(405, { error: "POST only" });
  if (!URL || !SERVICE_KEY || !ANON_KEY || !MAIL_SECRET) return reply(503, { error: "Email unavailable" });

  const bearer = req.headers.get("authorization")?.match(/^Bearer (.+)$/i)?.[1];
  if (!bearer) return reply(401, { error: "Sign in first" });
  const { data: auth, error: authError } = await db.auth.getUser(bearer);
  const email = auth.user?.email;
  if (authError || !email) return reply(401, { error: "Sign in first" });

  let clientId: string;
  try {
    clientId = String((await req.json()).client_id || "");
  } catch {
    return reply(400, { error: "Invalid request" });
  }
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(clientId)) {
    return reply(400, { error: "Invalid kid ID" });
  }

  const { data: parent } = await db.from("redesign_parent_users")
    .select("id").eq("email", email.toLowerCase()).maybeSingle();
  if (!parent) return reply(403, { error: "Kid not linked to this parent" });
  const { data: kid } = await db.from("redesign_kid_profiles")
    .select("client_id, display_name").eq("client_id", clientId)
    .eq("parent_user_id", parent.id).maybeSingle();
  if (!kid) return reply(403, { error: "Kid not linked to this parent" });

  // Preserve the RPC's own auth.email()/RLS checks, in addition to the
  // explicit parent/kid relationship check above.
  const callerDb = createClient(URL, ANON_KEY, {
    global: { headers: { Authorization: `Bearer ${bearer}` } },
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { data: code, error: codeError } = await callerDb.rpc("generate_parent_recovery_code", {
    p_client_id: clientId,
  });
  if (codeError || !code) return reply(500, { error: "Could not create recovery code" });

  const name = escapeHtml(String(kid.display_name || "your kid").slice(0, 80));
  const safeCode = escapeHtml(String(code));
  const html = `<div style="font-family:sans-serif;padding:24px"><h2>Recovery code for ${name}</h2>` +
    `<p>Enter this code in kidsnews to recover ${name}'s reading history:</p>` +
    `<p style="font-size:32px;font-weight:bold">${safeCode}</p>` +
    `<p>Single-use; expires in 24 hours. If you did not request this, ignore this email.</p></div>`;
  const sent = await fetch(`${URL}/functions/v1/send-email-v2`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-internal-secret": MAIL_SECRET },
    body: JSON.stringify({ to_email: email, subject: `kidsnews recovery code for ${kid.display_name || "your kid"}`,
      html, message: `Recovery code for ${kid.display_name || "your kid"}: ${code}`, from_name: "kidsnews" }),
  });
  if (!sent.ok) return reply(502, { error: "Could not send recovery email" });
  return reply(200, { success: true });
});
