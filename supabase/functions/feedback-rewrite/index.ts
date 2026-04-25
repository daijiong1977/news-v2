// feedback-rewrite — Supabase Edge Function for the article "Think & share" tab.
//
// Browser POSTs the kid's free-form response; this function:
//   1. Validates ≥20 words.
//   2. Calls DeepSeek (chat with json_object response_format) to score the
//      writing on 4 dims, write warm specific feedback, and rewrite the
//      response keeping the kid's voice + ideas.
//   3. INSERTs a row into redesign_user_responses for cross-device history.
//
// No login. The browser sends an anonymous `client_id` (uuid stored in
// localStorage). verify_jwt is OFF — function is public-callable; rate-
// limit / abuse handling is a follow-up.
//
// Env required:
//   DEEPSEEK_API_KEY            — DeepSeek bearer token
//   SUPABASE_URL                — auto-injected
//   SUPABASE_SERVICE_ROLE_KEY   — auto-injected (used to write the response row)
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";

const DEEPSEEK_KEY = Deno.env.get("DEEPSEEK_API_KEY") ?? "";
const SB_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SB_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ??
                       Deno.env.get("SUPABASE_SERVICE_KEY") ?? "";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, apikey",
  "Access-Control-Max-Age": "86400",
};

const SYSTEM_PROMPT = `You are a friendly writing coach for kids ages 8-13.
A kid just wrote a short response to a news story they read. Your job:

1. SCORE their writing on 4 dimensions (each 1-5, where 5 = excellent for
   their age):
     - clarity: Is the main idea clear?
     - evidence: Did they cite specific things from the story?
     - voice: Does it sound like a real kid thinking, not a template?
     - depth: Did they go beyond the obvious "this is interesting"?

2. FEEDBACK — 2-3 sentences, warm + specific. Mention what they did
   well, then ONE concrete thing to try next time. NEVER condescend.
   Example tone: "I loved how you connected the cow's tool-use to your
   own dog. Next time, try one specific number from the story — it makes
   readers picture it."

3. REWRITE their response. Keep their voice + their core ideas. Make
   the structure clearer; weave in ONE specific detail from the article
   they could have included; tighten any rambling. Same length or up
   to +50% longer. Wrap a single phrase the kid uniquely contributed
   in **double asterisks** so they can see "this part is yours, I just
   sharpened around it."

OUTPUT — valid JSON only, no markdown fences:
{
  "scores": {"clarity": N, "evidence": N, "voice": N, "depth": N},
  "feedback": "...",
  "rewrite": "..."
}`;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") {
    return jsonResponse({ error: "method not allowed" }, 405);
  }
  if (!DEEPSEEK_KEY) {
    return jsonResponse({ error: "server misconfigured: DEEPSEEK_API_KEY missing" }, 500);
  }

  let payload: any;
  try {
    payload = await req.json();
  } catch {
    return jsonResponse({ error: "invalid JSON body" }, 400);
  }

  const text = String(payload.text || "").trim();
  const articleId = String(payload.articleId || "").trim();
  const articleTitle = String(payload.articleTitle || "").slice(0, 300);
  const articleSummary = String(payload.articleSummary || "").slice(0, 2000);
  const level = ["Sprout", "Tree"].includes(payload.level) ? payload.level : null;
  const clientId = String(payload.clientId || "").trim();

  if (!text || !articleId || !clientId) {
    return jsonResponse({
      error: "missing fields: need text, articleId, clientId",
    }, 400);
  }
  const wordCount = text.split(/\s+/).filter(Boolean).length;
  if (wordCount < 20) {
    return jsonResponse({
      error: `Need at least 20 words. You wrote ${wordCount}.`,
      word_count: wordCount,
      min_words: 20,
    }, 400);
  }
  if (wordCount > 500) {
    return jsonResponse({
      error: `Too long — max 500 words. You wrote ${wordCount}.`,
    }, 400);
  }

  // Build the user message with article context the model needs to coach well
  const userMsg = `Article title: ${articleTitle || "(unknown)"}
Article summary (first 2KB): ${articleSummary}
Reader level: ${level || "Sprout"}

Kid's response (${wordCount} words):
${text}

Score, give feedback, and rewrite per the system prompt.`;

  // Call DeepSeek chat with json_object response_format
  let dsBody: any;
  try {
    const ds = await fetch("https://api.deepseek.com/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${DEEPSEEK_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "deepseek-v4-flash",
        // chat/rewrite path — thinking off (V4 default is on)
        thinking: { type: "disabled" },
        messages: [
          { role: "system", content: SYSTEM_PROMPT },
          { role: "user", content: userMsg },
        ],
        response_format: { type: "json_object" },
        temperature: 0.4,
        max_tokens: 1500,
      }),
    });
    if (!ds.ok) {
      const errText = await ds.text();
      return jsonResponse({
        error: "DeepSeek upstream error",
        status: ds.status,
        detail: errText.slice(0, 300),
      }, 502);
    }
    dsBody = await ds.json();
  } catch (e) {
    return jsonResponse({
      error: "DeepSeek network error",
      detail: String(e).slice(0, 300),
    }, 502);
  }

  let parsed: any;
  try {
    parsed = JSON.parse(dsBody.choices[0].message.content);
  } catch {
    return jsonResponse({
      error: "DeepSeek returned malformed JSON",
      raw: String(dsBody.choices?.[0]?.message?.content || "").slice(0, 300),
    }, 502);
  }

  // Persist (best-effort — never block the response on DB write failure)
  let savedId: string | null = null;
  if (SB_URL && SB_SERVICE_KEY) {
    try {
      const sb = createClient(SB_URL, SB_SERVICE_KEY);
      const { data, error } = await sb
        .from("redesign_user_responses")
        .insert({
          client_id: clientId,
          article_id: articleId,
          level: level,
          response_text: text,
          response_word_count: wordCount,
          ai_feedback: parsed.feedback || null,
          ai_rewrite: parsed.rewrite || null,
          ai_scores: parsed.scores || null,
        })
        .select("id")
        .single();
      if (!error && data) savedId = data.id;
    } catch {
      // swallow — response still returned to user
    }
  }

  return jsonResponse({
    feedback: parsed.feedback ?? "",
    rewrite: parsed.rewrite ?? "",
    scores: parsed.scores ?? {},
    word_count: wordCount,
    saved_id: savedId,
  });
});
