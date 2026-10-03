import { encoder, hash, validateBundle, type Files } from './bundle.ts';
export interface PublicationIO {
  publicMatches(files: Files): Promise<void>;
  newer(date: string, startedAt: string, packageId: string): Promise<boolean>;
  put(name: string, data: Uint8Array, mime: string): Promise<void>;
  index(): Promise<string[]>;
  commit(value: Awaited<ReturnType<typeof validateBundle>>): Promise<void>;
  done(packageId: string): Promise<void>;
}
export async function finalizePackage(bytes: Uint8Array, ready: Record<string, string>, site: string, io: PublicationIO) {
  const value = await validateBundle(bytes);
  const {files, manifest} = value;
  if (manifest.shell !== 'provided' || ready.package_id !== manifest.package_id || ready.site_url !== site || ready.zip_sha256 !== await hash(bytes)) throw Error('ready/target/shell mismatch');
  await io.publicMatches(files);
  if (await io.newer(manifest.date, manifest.started_at, manifest.package_id)) throw Error('superseded revision');
  // Read/validate the existing index BEFORE any writes; a read failure cannot reset it.
  let dates = await io.index();
  if (!Array.isArray(dates) || dates.some(x => !/^\d{4}-\d{2}-\d{2}$/.test(x))) throw Error('archive-index invalid');
  await io.put(`bot-versions/${manifest.date}/${manifest.package_id}.zip`, bytes, 'application/zip');
  for (const [name, content] of Object.entries(files)) {
    if (name.startsWith('payloads/') || name.startsWith('article_payloads/') || name.startsWith('article_images/')) {
      await io.put(`${manifest.date}/${name}`, content, name.endsWith('.json') ? 'application/json' : 'image/webp');
    }
  }
  await io.publicMatches(files);
  await io.commit(value); // DB stories + search + source cadence + receipt, single transaction.
  if (!dates.length || manifest.date >= dates.slice().sort().reverse()[0]) await io.put('latest.zip', bytes, 'application/zip');
  await io.put(`${manifest.date}.zip`, bytes, 'application/zip');
  await io.put(`${manifest.date}-manifest.json`, files['publication-manifest.json'], 'application/json');
  dates = [...new Set([...dates, manifest.date])].sort().reverse().slice(0, 30);
  await io.put('archive-index.json', encoder.encode(JSON.stringify({dates, updated_at: new Date().toISOString()})), 'application/json');
  await io.done(manifest.package_id); // Last marker; failures before here are resumable.
  return manifest;
}
