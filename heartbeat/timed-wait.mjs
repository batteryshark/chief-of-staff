import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import path from 'node:path';

export function docketReader(source) {
  if (!path.isAbsolute(source)) throw Error('Explicit installed Docket client source required');
  return id => new Promise((resolve, reject) => {
    execFile('python3', ['-B', fileURLToPath(new URL('./docket-read.py', import.meta.url)), source, id], { timeout: 7000, maxBuffer: 24000 }, (error, stdout) => {
      if (error) return reject(Error('Known Docket item unavailable; no fallback/restart'));
      try { resolve(JSON.parse(stdout)); } catch { reject(Error('Invalid Docket item response')); }
    });
  });
}
export function docketBinding(item, origin, now, fired = false) {
  if (!/^dkt_[A-Za-z0-9]+$/.test(item?.id ?? '') || !['timer','alarm'].includes(item.kind)
      || item.target?.session_id !== origin.sessionID || item.target?.directory !== origin.directory) throw Error('Docket item/origin/directory mismatch');
  const fire = Date.parse(item.fire_at);
  if (!Number.isFinite(fire) || (fired ? fire > now || !['firing','admitted','delivered'].includes(item.status) : fire <= now || item.status !== 'pending')) throw Error('Docket item not eligible for this wait/wake');
  return { id: item.id, kind: item.kind, fire_at: item.fire_at, target: item.target,
    contextDigest: createHash('sha256').update(JSON.stringify(item.context ?? {})).digest('hex') };
}
