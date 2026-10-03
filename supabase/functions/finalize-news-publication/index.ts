// Scheduler-only opt-in worker. Bot uploads ZIP + ready marker, never calls this.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";
import { encoder, hash, type Files } from "./bundle.ts";
import { finalizePackage } from './worker.ts';
const active = Deno.env.get("KIDSNEWS_PUBLICATION_ENABLED") === "true";
const schedulerSecret = Deno.env.get("KIDSNEWS_PUBLICATION_SCHEDULER_SECRET");
const publicSite = Deno.env.get("KIDSNEWS_PUBLICATION_SITE_URL");
const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  {auth: {persistSession: false, autoRefreshToken: false}});
const pending = sb.storage.from("kidsnews-publication-pending");
const archive = sb.storage.from("redesign-daily-content");

async function publicMatches(files: Files) {
  if (!publicSite || !["https://kidsnews.21mins.com", "https://news.6ray.com"].includes(publicSite)) throw Error("unapproved public target");
  for (const [name, content] of Object.entries(files)) {
    if (!name.startsWith("payloads/") && !name.startsWith("article_payloads/") && !name.startsWith("article_images/") && name !== "publication-manifest.json") continue;
    const response = await fetch(`${publicSite}/${name}`, {redirect: "error", signal: AbortSignal.timeout(8000)});
    if (!response.ok || await hash(new Uint8Array(await response.arrayBuffer())) !== await hash(content)) throw Error(`public mismatch: ${name}`);
  }
}
async function put(name: string, body: Uint8Array, mime: string) {
  const {error} = await archive.upload(name, body, {upsert: true, contentType: mime});
  if (error) throw Error(`archive upload failed: ${name}`);
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST" || !schedulerSecret || req.headers.get("authorization") !== `Bearer ${schedulerSecret}`) return new Response("Forbidden", {status: 403});
  if (!active) return new Response("Publication worker not activated", {status: 503});
  const owner = crypto.randomUUID();
  const results: {package_id: string; status: string}[] = [];
  const {data: claimed, error: claimError} = await sb.rpc("claim_kidsnews_publication_worker", {p_owner: owner});
  if (claimError || !claimed) return Response.json({ok: false, reason: "worker busy or claim failed"}, {status: 409});
  try {
    const {data: entries, error} = await pending.list("pending", {limit: 100, sortBy: {column: "created_at", order: "desc"}});
    if (error) throw Error("pending list failed");
    // One package per tick: bounded execution/lease. Poison packages cannot block others.
    const completed = new Set((entries || []).filter(x => x.name.endsWith(".done.json")).map(x => x.name.split(".")[0]));
    for (const entry of (entries || []).filter(x => /^[a-f0-9]{64}\.ready\.json$/.test(x.name))) {
      const packageId = entry.name.split(".")[0];
      if (completed.has(packageId)) continue;
      try {
        const {data: readyBlob, error: readyError} = await pending.download(`pending/${entry.name}`);
        const {data: blob, error: zipError} = await pending.download(`pending/${packageId}.zip`);
        if (readyError || zipError || !blob || !readyBlob || readyBlob.size > 16384) throw Error("missing package/ready marker");
        const bytes = new Uint8Array(await blob.arrayBuffer());
        const ready = JSON.parse(await readyBlob.text());
        if (ready.package_id !== packageId) throw Error('ready package mismatch');
        await finalizePackage(bytes, ready, publicSite || '', {
          publicMatches,
          async newer(date, startedAt, id) {
            const {data, error} = await sb.from('kidsnews_publication_receipts').select('package_id')
              .eq('run_date', date).gte('revision', startedAt).neq('package_id', id).limit(1);
            if (error) throw Error('receipt read failed');
            return !!data?.length;
          },
          async put(name, content, mime) {
            const {data, error} = await sb.rpc('claim_kidsnews_publication_worker', {p_owner: owner});
            if (error || !data) throw Error('worker lease lost');
            await put(name, content, mime);
          },
          async index() {
            const {data, error} = await archive.download('archive-index.json');
            if (error || !data) throw Error('archive-index read failed');
            return JSON.parse(await data.text()).dates;
          },
          async commit(value) {
            const {error} = await sb.rpc('commit_kidsnews_publication', {
              p_owner: owner, p_manifest: value.manifest, p_stories: value.stories,
              p_search: value.search, p_usage: value.usage});
            if (error) throw Error('publication transaction failed');
          },
          async done(id) {
            const {error} = await pending.upload(`pending/${id}.done.json`, encoder.encode(JSON.stringify({package_id: id,
              completed_at: new Date().toISOString()})), {upsert: false, contentType: 'application/json'});
            if (error) throw Error('receipt marker upload failed');
          },
        });
        results.push({package_id: packageId, status: "complete"});
        break;
      } catch (exc) {
        console.error("publication package failed", packageId, exc instanceof Error ? exc.message : "unknown error");
        results.push({package_id: packageId, status: "failed"});
        if (results.length >= 3) break;
      }
    }
    return Response.json({ok: !results.some(x => x.status === "failed"), results});
  } finally {
    await sb.rpc("claim_kidsnews_publication_worker", {p_owner: owner, p_release: true});
  }
});
