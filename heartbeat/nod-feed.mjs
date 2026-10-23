// Finite known-new-request pass for the existing chief-nod runner. No creation/delivery.
import { readFile, writeFile, rename } from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { Bus, state } from './bus.mjs';
import { NodAdapter } from './nod.mjs';

export async function checkKnown(options, { run, now = Date.now, limit = 4 } = {}) {
  if (options.nodReadEnabled !== true || !Array.isArray(options.nodCommand)) throw Error('Explicit Nod read opt-in required');
  if (!Number.isInteger(limit) || limit < 1 || limit > 4) throw Error('Read pass limit is 1..4');
  const bus = new Bus(options.memoryRoot), rows = await bus.rows(), events = state(rows).events;
  const known = [...new Map(rows.filter(r => r.type === 'nod-request' && r.mode === 'new-bus-only').map(r => [r.requestID, r])).values()];
  const checked = new Map(rows.filter(r => r.type === 'nod-check').map(r => [r.requestID, r]));
  const pollFile = path.join(options.memoryRoot, 'nod-polls.json');
  let polls = {};
  try { polls = JSON.parse(await readFile(pollFile, 'utf8')); } catch(e) { if(e.code !== 'ENOENT') throw e; }
  for(const [id,value] of Object.entries(polls)) checked.set(id,value);
  const due = known.filter(r => !rows.some(a => a.type === 'nod-answer' && a.requestID === r.requestID
      && (a.answer?.decision || ['answered','completed','decided'].includes(a.answer?.status)))
    && events.some(e => e.id === r.event && !e.closed) && (checked.get(r.requestID)?.nextCheck ?? 0) <= now())
    .sort((a, b) => (checked.get(a.requestID)?.at ?? 0) - (checked.get(b.requestID)?.at ?? 0)).slice(0, limit);
  const adapter = new NodAdapter(bus, { command: options.nodCommand, ...(run ? { run } : {}) });
  let failures = 0;
  for (const row of due) {
    let ok = true;
    try { await adapter.check(row.requestID); } catch { ok = false; failures++; }
    await bus.transaction(async () => {
      let current = {};
      try { current = JSON.parse(await readFile(pollFile,'utf8')); } catch(e) { if(e.code !== 'ENOENT') throw e; }
      current[row.requestID] = { at: now(), nextCheck: now() + (ok ? 30000 : 60000), ok };
      const temp = pollFile + '.' + randomUUID();
      await writeFile(temp, JSON.stringify(current) + '\n', {mode:0o600,flag:'wx'});
      await rename(temp,pollFile);
    });
  }
  return { checked: due.length, failures, knownRequestIDs: known.map(r => r.requestID) };
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  const [flag, file] = process.argv.slice(2);
  if (flag !== '--options' || !file?.startsWith('/')) throw Error('Explicit installed options required');
  try { console.log(JSON.stringify(await checkKnown(JSON.parse(await readFile(file, 'utf8'))))); }
  catch { console.error('Known bus read failed; no legacy fallback or delivery'); process.exitCode = 1; }
}
