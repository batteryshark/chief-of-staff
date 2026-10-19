// Local, synchronous metadata/receipt helpers. No network or transport imports.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';

const id = x => typeof x === 'string' && /^[a-z][a-z0-9-]{0,47}$/.test(x);
const session = x => typeof x === 'string' && /^ses_[A-Za-z0-9]+$/.test(x);
const keys = (x, names) => x && typeof x === 'object' && !Array.isArray(x) && Object.keys(x).sort().join() === names.sort().join();
const absolute = x => typeof x === 'string' && path.isAbsolute(x) && path.normalize(x) === x;
export function validateDirectory(data) {
  if (!keys(data, ['version','domains']) || data.version !== 1 || !Array.isArray(data.domains)) throw Error('invalid domain directory');
  const ids = new Set(), homes = new Set();
  for (const row of data.domains) {
    if (!keys(row, ['id','responsibility','server','home','pointer']) || !id(row.id) ||
        typeof row.responsibility !== 'string' || !row.responsibility.trim() || row.server !== 'local' ||
        !absolute(row.home) || row.pointer !== path.join(row.home, 'chief.json')) throw Error('invalid local domain');
    if (ids.has(row.id) || homes.has(row.home)) throw Error('ambiguous domain directory');
    ids.add(row.id); homes.add(row.home);
  }
  return data;
}
export const loadDirectory = file => validateDirectory(JSON.parse(fs.readFileSync(file, 'utf8')));
export function resolveOwner(file, owner, {now=Date.now()}={}) {
  const row = loadDirectory(file).domains.find(r => r.id === owner);
  if (!row) throw Error('unknown owner: clarify once, do not forward again');
  if (fs.realpathSync(row.home) !== row.home || fs.lstatSync(row.pointer).isSymbolicLink()) throw Error('linked owner metadata');
  const pointer = JSON.parse(fs.readFileSync(row.pointer, 'utf8'));
  const updated = typeof pointer.updated === 'string' ? Date.parse(pointer.updated) : NaN;
  if (!session(pointer.session) || pointer.directory !== row.home || !Number.isFinite(updated) ||
      updated > now + 60000) throw Error('missing or malformed owner pointer');
  // Rotation timestamp, NOT a heartbeat. Liveness requires actual session checks.
  return {...row, session:pointer.session, pointerAgeMs:Math.max(0,now-updated), to:`${row.server}/${pointer.session}`};
}
export function validateHandoff(e) {
  if (!keys(e, ['version','id','origin','owner','action','principal_attribution','content']) || e.version !== 1 ||
      typeof e.id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(e.id) ||
      !keys(e.origin,['domain','session']) || !id(e.origin.domain) || !session(e.origin.session) || !id(e.owner) ||
      !['record-idea','review'].includes(e.action) || typeof e.principal_attribution !== 'string' || !e.principal_attribution.trim() ||
      typeof e.content !== 'string' || !e.content.trim() || e.content.length > 50000) throw Error('invalid attributed handoff');
  return e;
}
export function prepareHandoff(file, envelope, options) {
  validateHandoff(envelope);
  const directory = loadDirectory(file);
  if (!directory.domains.some(d => d.id === envelope.origin.domain)) throw Error('unknown origin');
  if (envelope.origin.domain === envelope.owner) throw Error('self handoff refused');
  const owner = resolveOwner(file, envelope.owner, options);
  return {to:owner.to, text:JSON.stringify(envelope), expectReply:true}; // Feed to existing a2a_send only.
}
// Sender persists this state in its OWN log. No retry, scheduler, send, or ack loop.
export function deliveryOutcome(state, event) {
  if (event === 'timeout') return {...state, status:'unresolved', send:false};
  if (event === 'unknown-owner') return {...state, status:state.clarified ? 'blocked' : 'needs-clarification', clarified:true, send:false};
  if (event === 'receipt') return {...state, status:'acknowledged', send:false};
  throw Error('unknown delivery event');
}
function privatePaths(home, names) {
  if (fs.realpathSync(home) !== home) throw Error('noncanonical receipt home');
  for (const name of names) {
    const file = path.join(home,name);
    try { if (fs.lstatSync(file).isSymbolicLink()) throw Error('linked private receipt file'); }
    catch (e) { if (e.code !== 'ENOENT') throw e; }
  }
}
function atomic(file, text) {
  const temp = file + '.pending';
  const fd = fs.openSync(temp, 'wx', 0o600);
  try { fs.writeFileSync(fd,text); } finally { fs.closeSync(fd); }
  try { fs.renameSync(temp,file); } finally { if (fs.existsSync(temp)) fs.unlinkSync(temp); }
}
export function receiveHandoff(file, receiver, ownHome, envelope) {
  validateHandoff(envelope);
  const directory = loadDirectory(file);
  if (!directory.domains.some(r=>r.id===envelope.origin.domain)) throw Error('unknown origin');
  const owner = directory.domains.find(r=>r.id===receiver);
  if (!owner || owner.home !== ownHome || envelope.owner !== receiver) throw Error('not this memory owner');
  if (envelope.action === 'record-idea' && receiver !== 'technical') throw Error('technical idea belongs to technical owner');
  privatePaths(ownHome,['handoffs.json','ideas.md','.handoff.lock','handoffs.json.pending','ideas.md.pending']);
  const lock = path.join(ownHome,'.handoff.lock');
  const fd = fs.openSync(lock,'wx',0o600); // Single owner writer; stale lock needs explicit reconciliation.
  try {
    const receiptFile = path.join(ownHome,'handoffs.json');
    const receipts = fs.existsSync(receiptFile) ? JSON.parse(fs.readFileSync(receiptFile,'utf8')) : {};
    if (!receipts || typeof receipts!=='object' || Array.isArray(receipts)) throw Error('malformed private receipts');
    const digest = createHash('sha256').update(JSON.stringify([envelope.id,envelope.origin.domain,envelope.origin.session,envelope.owner,envelope.action,envelope.principal_attribution,envelope.content])).digest('hex');
    if (Object.hasOwn(receipts,envelope.id)) {
      if (receipts[envelope.id].digest !== digest) throw Error('handoff id reused with different content');
      return receipts[envelope.id];
    }
    if (envelope.action === 'record-idea') {
      const ideaFile = path.join(ownHome,'ideas.md');
      const ideas = fs.existsSync(ideaFile) ? fs.readFileSync(ideaFile,'utf8') : '# Ideas\n';
      const prefix = `<!-- handoff:${envelope.id} `, marker = `${prefix}${digest} -->`;
      if (ideas.includes(prefix) && !ideas.includes(marker)) throw Error('idea id/content conflict');
      // Marker dedupes recovery if interrupted between idea and receipt writes.
      if (!ideas.includes(marker)) atomic(ideaFile,ideas+`\n${marker}\nOrigin: ${envelope.origin.domain}/${envelope.origin.session}; principal: ${envelope.principal_attribution}\n\n${envelope.content}\n`);
    }
    const receipt = {id:envelope.id, owner:receiver, status:envelope.action === 'record-idea' ? 'recorded' : 'accepted', digest};
    receipts[envelope.id] = receipt;
    atomic(receiptFile,JSON.stringify(receipts,null,2)+'\n');
    return receipt; // Return on automatic a2a reply, NEVER call send to acknowledge.
  } finally { fs.closeSync(fd); fs.unlinkSync(lock); }
}
