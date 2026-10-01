// Pure contract validation; no credentials, network, DB, or deployment.
import { unzipSync } from "npm:fflate@0.8.2";
export const decoder = new TextDecoder();
export const encoder = new TextEncoder();
export type Files = Record<string, Uint8Array>;
export interface Manifest {
  schema_version: number; package_id: string; run_id: string; date: string;
  started_at: string; shell: string; counts: Record<string, number>; files: Record<string, string>;
}
export interface Story {
  category: string; story_slot: number; published_date: string; payload_story_id: string;
  source_config_id: number | null; source_url: string; source_name: string; source_title: string;
  facts_supported: boolean; event_clear: boolean; safety_scores: Record<string, number>;
}
export function json<T>(data: Uint8Array): T { return JSON.parse(decoder.decode(data)); }
export async function hash(data: Uint8Array): Promise<string> {
  return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", data as Uint8Array<ArrayBuffer>)))
    .map(x => x.toString(16).padStart(2, "0")).join("");
}
export function safeName(name: string): boolean {
  return !!name && !name.startsWith("/") && !/[\\:]/.test(name) &&
    name.split("/").every(x => !!x && x !== "." && x !== "..");
}
export function boundedUnzip(data: Uint8Array): Files {
  if (data.length > 20 * 1024 * 1024) throw Error("compressed budget");
  // Check central-directory sizes BEFORE decompression, not after a zip bomb.
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  let end = data.length - 22;
  while (end >= Math.max(0, data.length - 65557) && view.getUint32(end, true) !== 0x06054b50) end--;
  if (end < 0 || view.getUint32(end, true) !== 0x06054b50) throw Error("ZIP directory missing");
  const count = view.getUint16(end + 10, true);
  if (!count || count > 200 || view.getUint16(end + 4, true) || view.getUint16(end + 6, true)) throw Error("ZIP count/disk");
  let offset = view.getUint32(end + 16, true), total = 0;
  const names = new Set<string>();
  for (let n = 0; n < count; n++) {
    if (offset + 46 > end || view.getUint32(offset, true) !== 0x02014b50) throw Error("bad ZIP directory");
    const size = view.getUint32(offset + 24, true), nameLength = view.getUint16(offset + 28, true);
    const name = decoder.decode(data.subarray(offset + 46, offset + 46 + nameLength));
    const attrs = view.getUint32(offset + 38, true);
    if (!safeName(name) || names.has(name) || size > 5 * 1024 * 1024 || ((attrs >>> 16) & 0xf000) === 0xa000) throw Error("unsafe ZIP file");
    names.add(name); total += size;
    if (total > 80 * 1024 * 1024) throw Error("expanded budget");
    offset += 46 + nameLength + view.getUint16(offset + 30, true) + view.getUint16(offset + 32, true);
  }
  if (offset !== end) throw Error("ZIP directory mismatch");
  const files = unzipSync(data);
  if (Object.keys(files).length !== count || Object.entries(files).some(([name, value]) => !names.has(name) || value.length > 5 * 1024 * 1024)) throw Error("ZIP local/central mismatch");
  return files;
}
export async function validateBundle(data: Uint8Array) {
  const files = boundedUnzip(data);
  const manifest = json<Manifest>(files["publication-manifest.json"]);
  if (manifest.schema_version !== 1 || !/^\d{4}-\d{2}-\d{2}$/.test(manifest.date) ||
    !/^[a-f0-9]{64}$/.test(manifest.package_id) || !/^[a-f0-9-]{36}$/.test(manifest.run_id) ||
    !Number.isFinite(Date.parse(manifest.started_at))) throw Error("invalid manifest");
  const hashes: Record<string, string> = {};
  for (const name of Object.keys(files).filter(x => x !== "publication-manifest.json").sort()) hashes[name] = await hash(files[name]);
  const canonical = JSON.stringify(hashes);
  if (JSON.stringify(Object.fromEntries(Object.entries(manifest.files).sort(([a], [b]) => a.localeCompare(b, "en")))) !== canonical) {
    // Locale collation can differ from Python; compare key sets + values instead.
    if (Object.keys(manifest.files).length !== Object.keys(hashes).length ||
        Object.entries(hashes).some(([n, h]) => manifest.files[n] !== h)) throw Error("file hashes mismatch");
  }
  if (await hash(encoder.encode(canonical)) !== manifest.package_id) throw Error("package hash mismatch");
  const stories = json<Story[]>(files["publication-records.json"]);
  const usage = json<{source_id: number; used_date: string}[]>(files["source-usage.json"]);
  if (!Array.isArray(stories) || !stories.length || stories.length > 9) throw Error("empty/oversized stories");
  const search: Record<string, unknown>[] = [];
  const ids = new Set<string>();
  const dims = ["violence", "sexual", "substance", "language", "fear", "adult_themes", "distress", "bias"];
  for (const category of ["News", "Science", "Fun"]) {
    const rows = stories.filter(x => x.category === category);
    if (rows.length > 3 || manifest.counts[category.toLowerCase()] !== rows.length) throw Error("counts mismatch");
    const expected = rows.map((_, i) => `${manifest.date}-${category.toLowerCase()}-${i + 1}`);
    for (const [i, row] of rows.entries()) {
      if (row.payload_story_id !== expected[i] || row.story_slot !== i + 1 || row.published_date !== manifest.date ||
          row.facts_supported !== true || row.event_clear !== true || ids.has(row.payload_story_id)) throw Error("unqualified story");
      ids.add(row.payload_story_id);
      const scores = row.safety_scores;
      if (Object.keys(scores).length !== 8 || dims.some(d => !Number.isFinite(scores[d]) || scores[d] < 0 || scores[d] > 5)) throw Error("safety evidence missing");
      if (dims.some(d => scores[d] >= (["sexual", "substance", "language"].includes(d) || (d === "bias" && category === "News") ? 3 : 4))) throw Error("unsafe story");
    }
    for (const level of ["easy", "middle", "cn"]) {
      const listing = json<{articles: Record<string, unknown>[]}>(files[`payloads/articles_${category.toLowerCase()}_${level}.json`]).articles;
      if (JSON.stringify(listing.map(x => x.id)) !== JSON.stringify(expected)) throw Error("listing IDs mismatch");
      for (const [i, card] of listing.entries()) {
        const body = level === "cn" ? card : json<Record<string, unknown>>(files[`article_payloads/payload_${card.id}/${level}.json`]);
        if (level !== "cn") {
          const count = String(body.summary).trim().split(/\s+/).length;
          const short = category === "Fun" && Number(body.source_word_count) < 350;
          const lo = category === "Fun" ? (level === "easy" ? (short ? 120 : 140) : 180) : (level === "easy" ? 140 : 300);
          const hi = category === "Fun" && short ? (level === "easy" ? 220 : 350) :
            (category === "Science" ? (level === "easy" ? 320 : 520) : (level === "easy" ? 270 : 410));
          if (count < lo || count > hi || body.source_url !== rows[i].source_url) throw Error("body/source mismatch");
        }
        if (card.image_url) {
          const name = String(card.image_url).replace(/^\//, "");
          if (!name.startsWith("article_images/") || !files[name]) throw Error("image missing");
        }
        search.push({story_id: card.id, published_date: manifest.date, category, level: level === "cn" ? "zh" : level,
          title: card.title, summary: body.summary, why: body.why_it_matters || "",
          keywords: (body.keywords as {term: string}[] || []).map(x => x.term),
          image_url: card.image_url || "", source_name: rows[i].source_name});
      }
    }
  }
  if (ids.size !== stories.length) throw Error("unknown category");
  const sourceIds = new Set(stories.map(x => x.source_config_id).filter(x => x !== null));
  if (usage.length !== sourceIds.size || new Set(usage.map(x => x.source_id)).size !== usage.length ||
    usage.some(x => !Number.isInteger(x.source_id) || x.source_id <= 0 || !sourceIds.has(x.source_id) || x.used_date !== manifest.date)) throw Error("source usage mismatch");
  return {files, manifest, stories, usage, search};
}
