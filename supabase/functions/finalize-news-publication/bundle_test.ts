import { zipSync } from 'npm:fflate@0.8.2';
import { boundedUnzip, encoder, hash, validateBundle } from './bundle.ts';
import { finalizePackage, type PublicationIO } from './worker.ts';

function assert(value: unknown, message = 'assertion failed'): asserts value { if (!value) throw Error(message); }
async function rejects(fn: () => unknown | Promise<unknown>) {
  let failed = false;
  try { await fn(); } catch { failed = true; }
  assert(failed, 'expected rejection');
}
async function fixture() {
  const path = Deno.env.get('KIDSNEWS_TEST_BUNDLE');
  if (!path) throw Error('Set KIDSNEWS_TEST_BUNDLE to the offline full-round publication.zip');
  const original = await validateBundle(await Deno.readFile(path));
  original.manifest.shell = 'provided'; // Fixture ONLY; no production shell or target is accessed.
  original.files['publication-manifest.json'] = encoder.encode(JSON.stringify(original.manifest));
  const data = zipSync(original.files);
  const ready = {package_id: original.manifest.package_id, zip_sha256: await hash(data), site_url: 'https://fixture.invalid'};
  return {data, ready};
}
function fakeIO() {
  const events: string[] = [], receipts = new Set<string>();
  let committed = 0;
  const io: PublicationIO = {
    async publicMatches() { events.push('verify'); },
    async newer() { events.push('newer'); return false; },
    async index() { events.push('read-index'); return ['2026-09-29']; },
    async put(name) { events.push(name); },
    async commit(value) { events.push('commit'); if (!receipts.has(value.manifest.package_id)) {
      committed++; receipts.add(value.manifest.package_id);
    } },
    async done() { events.push('done'); },
  };
  return {io, events, commits: () => committed};
}
Deno.test('Python full-round ZIP interoperates; nine records and 27 search rows', async () => {
  const {data} = await fixture();
  const value = await validateBundle(data);
  assert(value.stories.length === 9 && value.search.length === 27);
});
Deno.test('normal finalize: public proof -> files -> transaction -> archive index -> done', async () => {
  const {data, ready} = await fixture(), f = fakeIO();
  await finalizePackage(data, ready, ready.site_url, f.io);
  assert(f.events[0] === 'verify');
  assert(f.events.indexOf('commit') < f.events.indexOf('archive-index.json'));
  assert(f.events.at(-1) === 'done' && f.commits() === 1);
});
Deno.test('retry after post-commit archive failure does not double-insert DB', async () => {
  const {data, ready} = await fixture(), f = fakeIO();
  const original = f.io.put;
  f.io.put = async (name, bytes, mime) => { if (name === 'archive-index.json') throw Error('offline crash'); await original(name, bytes, mime); };
  await rejects(() => finalizePackage(data, ready, ready.site_url, f.io));
  assert(f.commits() === 1 && !f.events.includes('done'));
  f.io.put = original;
  await finalizePackage(data, ready, ready.site_url, f.io);
  assert(f.commits() === 1 && f.events.at(-1) === 'done');
});
Deno.test('failed public verification or superseded version causes zero writes', async () => {
  const {data, ready} = await fixture();
  for (const kind of ['site', 'superseded']) {
    const f = fakeIO();
    if (kind === 'site') f.io.publicMatches = async () => { throw Error('old public content'); };
    else f.io.newer = async () => true;
    await rejects(() => finalizePackage(data, ready, ready.site_url, f.io));
    assert(!f.events.includes('commit') && !f.events.some(x => x.endsWith('.zip')));
  }
});
Deno.test('archive-index read failure never resets previous archive', async () => {
  const {data, ready} = await fixture(), f = fakeIO();
  f.io.index = async () => { throw Error('connection failure'); };
  await rejects(() => finalizePackage(data, ready, ready.site_url, f.io));
  assert(f.commits() === 0 && !f.events.some(x => x.endsWith('.zip')));
});
Deno.test('ZIP traversal, duplicate/header sizes and corrupt content refused', async () => {
  await rejects(() => boundedUnzip(zipSync({'../evil': encoder.encode('bad')})));
  const {data} = await fixture();
  const files = boundedUnzip(data);
  files['source-usage.json'] = encoder.encode('[]');
  await rejects(() => validateBundle(zipSync(files)));
  const bomb = zipSync({'x': encoder.encode('small')});
  const view = new DataView(bomb.buffer);
  for (let i = 0; i < bomb.length - 46; i++) {
    if (view.getUint32(i, true) === 0x02014b50) { view.setUint32(i + 24, 100_000_000, true); break; }
  }
  await rejects(() => boundedUnzip(bomb));
});
