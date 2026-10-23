import { mkdir, open, readFile, rmdir, stat } from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

const delays = { urgent: 0, normal: 240_000, fyi: 840_000 };
export const claimDeadlineMs = 180_000;
export const questionFallbackMs = 300_000;
export const unansweredEscalationMs = 30 * 60_000;
const bounded = (v, n, name) => {
  if (typeof v !== 'string' || !v.trim() || v.length > n) throw Error(`Invalid ${name}`);
  return v;
};
export function state(rows) {
  const events = new Map();
  let active;
  for (const row of rows) {
    if (row.type === 'post') events.set(row.id, { ...row });
    if (row.type === 'claim') active = { ...row };
    if (row.type === 'session' && active?.id === row.batch) Object.assign(active, { sessionID: row.sessionID, parentID: row.parentID });
    if (row.type === 'claim-health' && active?.id === row.batch) active.health = row.status;
    if (row.type === 'dispatch-prompt' && active?.id === row.batch) active.promptStage = row.status;
    if (row.type === 'result') Object.assign(events.get(row.event), { result: row });
    if (row.type === 'close') Object.assign(events.get(row.event), { closed: row });
    if (row.type === 'finish' && active?.id === row.batch) active = undefined;
  }
  return { events: [...events.values()], active };
}

export class Bus {
  constructor(root, { now = Date.now, batchSize = 8 } = {}) {
    if (!path.isAbsolute(root)) throw Error('Absolute memory root required');
    if (!Number.isInteger(batchSize) || batchSize < 1 || batchSize > 8) throw Error('batchSize must be 1..8');
    this.root = root; this.now = now; this.batchSize = batchSize;
  }
  async rows() {
    let text;
    try { text = await readFile(path.join(this.root, 'events.jsonl'), 'utf8'); }
    catch (e) { if (e.code === 'ENOENT') return []; throw e; }
    // Do not hide torn/corrupt records. An operator must reconcile before resuming.
    if (text && !text.endsWith('\n')) throw Error('Incomplete journal tail; reconcile before resuming');
    return text.split('\n').filter(Boolean).map(line => JSON.parse(line));
  }
  async transaction(fn) {
    await mkdir(this.root, { recursive: true, mode: 0o700 });
    const lock = path.join(this.root, '.lock');
    // Bounded local contention; never steal a possibly live/stale lock.
    for (let tries = 0; ; tries++) {
      try { await mkdir(lock); break; }
      catch (e) {
        if (e.code !== 'EEXIST' || tries === 100) throw e;
        await new Promise(resolve => setTimeout(resolve, 10));
      }
    }
    try {
      const rows = await this.rows();
      const append = async row => {
        const file = await open(path.join(this.root, 'events.jsonl'), 'a', 0o600);
        try { await file.writeFile(JSON.stringify(row) + '\n'); await file.sync(); }
        finally { await file.close(); }
        // Also persist creation of the journal directory entry on the local filesystem.
        const dir = await open(this.root, 'r');
        try { await dir.sync(); } finally { await dir.close(); }
        rows.push(row);
      };
      return await fn(rows, append);
    } finally { await rmdir(lock); }
  }
  post(input, origin) {
    const { urgency, text, ref, key, limits } = input;
    if (!Object.hasOwn(delays, urgency)) throw Error('Invalid urgency');
    bounded(text, 4000, 'text'); bounded(ref, 256, 'ref'); bounded(key, 256, 'key');
    if (limits !== undefined) bounded(limits, 4000, 'original limits');
    bounded(origin.sessionID, 256, 'origin session');
    if (!path.isAbsolute(origin.directory)) throw Error('Absolute origin directory required');
    return this.transaction(async (rows, append) => {
      const old = state(rows).events.find(e => e.origin.sessionID === origin.sessionID && e.origin.directory === origin.directory && e.key === key);
      if (old) {
        if (old.text !== text || old.ref !== ref || old.urgency !== urgency || old.limits !== limits) throw Error('Stable key payload conflict');
        return old;
      }
      const event = { type: 'post', id: randomUUID(), at: this.now(), urgency, text, ref, key, ...(limits !== undefined ? { limits } : {}), origin: { ...origin } };
      await append(event); return event;
    });
  }
  claim() {
    return this.transaction(async (rows, append) => {
      const s = state(rows);
      if (s.active) return;
      const events = s.events.filter(e => !e.result && !e.closed && this.now() >= e.at + delays[e.urgency])
        .sort((a, b) => delays[a.urgency] - delays[b.urgency] || a.at - b.at).slice(0, this.batchSize);
      if (!events.length) return;
      const batch = { type: 'claim', id: randomUUID(), at: this.now(), events: events.map(e => e.id) };
      await append(batch); return { ...batch, items: events };
    });
  }
  bind(batch, sessionID, parentID) {
    return this.transaction(async (rows, append) => {
      if (state(rows).active?.id !== batch) throw Error('Not active batch');
      await append({ type: 'session', batch, sessionID, ...(parentID ? { parentID } : {}) });
    });
  }
  async active() { return state(await this.rows()).active; }
  promptStage(batch, status) {
    return this.transaction(async (rows, append) => {
      if (state(rows).active?.id !== batch) throw Error('Claim changed before prompt admission');
      await append({ type: 'dispatch-prompt', batch, status, at: this.now() });
    });
  }
  health(batch, status) {
    return this.transaction(async (rows, append) => {
      const active = state(rows).active;
      if (active?.id !== batch || active.health === status) return;
      await append({ type: 'claim-health', batch, status, at: this.now() });
    });
  }
  interruptIntent(batch) {
    return this.transaction(async (rows, append) => {
      if (state(rows).active?.id !== batch || rows.some(r => r.type === 'dispatcher-interrupt' && r.batch === batch)) return false;
      await append({ type: 'dispatcher-interrupt', batch, status: 'attempted-uncertain', at: this.now() });
      return true;
    });
  }
  async isDispatcher(sessionID) { return (await this.rows()).some(r => r.type === 'session' && r.sessionID === sessionID); }
  async status() {
    let lock, journalError, current;
    try { const s = await stat(path.join(this.root, '.lock')); lock = { inode: s.ino, modifiedAt: s.mtimeMs }; }
    catch (e) { if (e.code !== 'ENOENT') throw e; }
    try { current = state(await this.rows()); } catch (e) { journalError = e.message; }
    const rows = journalError ? [] : await this.rows();
    return { lock, journalError, active: current?.active,
      pendingReplies: current?.events.filter(e => e.result?.route === 'covered' && !rows.some(r => r.type === 'reply-outcome' && r.event === e.id && r.status === 'answer-admitted')).map(e => e.id),
      uncertainReplies: rows.filter(r => r.type === 'reply-attempt' && !rows.some(outcome => outcome.type === 'reply-outcome' && outcome.event === r.event && outcome.status === 'answer-admitted')).map(r => r.event),
      nodRequests: rows.filter(r => r.type === 'nod-intent').map(r => ({ event: r.event,
        requestID: rows.find(x => x.type === 'nod-request' && x.event === r.event)?.requestID,
        uncertain: rows.some(x => x.type === 'nod-uncertain' && x.event === r.event) || !rows.some(x => x.type === 'nod-request' && x.event === r.event) })) };
  }
  async recoverLock({ inode, noWriterConfirmed, note }) {
    // Operator-only action, not exposed to models. No age-based lease stealing.
    if (noWriterConfirmed !== true) throw Error('Explicit no-active-writer reconciliation required');
    bounded(note, 2000, 'reconciliation note');
    const lock = path.join(this.root, '.lock'), s = await stat(lock);
    if (s.ino !== inode) throw Error('Lock changed; refusing removal');
    await rmdir(lock); // Exact empty lock directory only; refuses unexpected contents.
    await this.transaction(async (_, append) => append({ type: 'lock-reconciled', inode, note, at: this.now() }));
  }
  answer(event, text) {
    bounded(text, 4000, 'chief answer');
    return this.transaction(async (rows, append) => {
      const old = rows.find(r => r.type === 'answer' && r.event === event);
      if (old) { if (old.text !== text) throw Error('Conflicting chief answer'); return old; }
      const e = state(rows).events.find(e => e.id === event);
      if (!e || e.closed || e.urgency === 'fyi') throw Error('Not an open chief inbox item');
      if (!e.result) await append({ type: 'result', event, route: 'chief', text: e.text, effect: 'none' });
      const row = { type: 'answer', event, text, at: this.now() }; await append(row);
      // Answered work leaves the question queue; delivery uncertainty remains in status/detail.
      await append({ type: 'close', event, text, at: this.now(), reason: 'chief-answer-recorded' });
      return row;
    });
  }
  recordClose(event, text, actor) {
    bounded(text, 4000, 'chief disposition');
    if (!actor?.sessionID || !actor.messageID || !actor.callID) throw Error('Native chief audit origin required');
    return this.transaction(async (rows, append) => {
      const e = state(rows).events.find(e => e.id === event);
      if (!e || e.urgency === 'fyi') throw Error('Exact chief inbox event required');
      const old = rows.find(r => r.type === 'chief-record-close' && r.event === event);
      if (old) {
        if (old.text !== text || old.actor.sessionID !== actor.sessionID) throw Error('Conflicting record-only disposition');
        return {status:'closed-record-only',event,delivery:'not-attempted',audit:old};
      }
      // Record-only acknowledgement cannot authorize or retry a reply. Existing
      // answer/uncertain reply/Nod provenance is immutable and remains inspectable.
      const audit = {type:'chief-record-close',event,text,actor:{...actor},at:this.now()};
      await append(audit);
      if (!e.closed) await append({type:'close',event,text,reason:'chief-record-only',actor:{...actor},at:this.now()});
      return {status:'closed-record-only',event,delivery:'not-attempted',audit};
    });
  }
  async deliver(event, send) {
    const admission = await this.transaction(async (rows, append) => {
      if (rows.some(r => r.type === 'chief-record-close' && r.event === event)) throw Error('Chief record-only close forbids delivery');
      if (rows.some(r => r.type === 'reply-attempt' && r.event === event)) return;
      const e = state(rows).events.find(e => e.id === event);
      const answer = rows.find(r => r.type === 'answer' && r.event === event);
      if (!e?.result || (e.result.route !== 'covered' && !answer)) throw Error('No authorized answer recorded');
      await append({ type: 'reply-attempt', event, at: this.now() });
      return { event: e, text: answer?.text ?? e.result.text };
    });
    if (!admission) return { status: 'already-attempted-no-replay' };
    let status;
    try { await send(admission); status = 'answer-admitted'; }
    catch { status = 'uncertain-no-replay'; }
    await this.transaction(async (_, append) => append({ type: 'reply-outcome', event, status, at: this.now() }));
    if (status === 'answer-admitted') await this.transaction(async (rows, append) => {
      if (!state(rows).events.find(e => e.id === event)?.closed)
        await append({ type: 'close', event, text: admission.text, at: this.now(), reason: 'answer-admitted' });
    });
    return { status };
  }
  finish(batch) {
    return this.transaction(async (rows, append) => {
      const s = state(rows);
      if (s.active?.id !== batch || !s.active.events.every(id => s.events.find(e => e.id === id)?.result)) throw Error('Incomplete batch; reconcile before resuming');
      await append({ type: 'finish', batch, at: this.now() });
    });
  }
  async inbox() {
    // A read is deliberately not a result, ACK, or close operation.
    const rows = await this.rows(), s = state(rows);
    const pending = s.events.filter(e => !e.closed && e.urgency !== 'fyi')
      .sort((a,b) => a.at - b.at || a.id.localeCompare(b.id));
    const entries = [];
    for (const e of pending) {
      const item = { id: e.id, origin: e.origin, ref: e.ref, urgency: e.urgency,
        ...(['chief','principal'].includes(e.result?.route) ? e.result : { route: 'chief', effect: 'pending-no-effect-replay', text: e.result?.text ?? e.text, needsReconciliation: true,
          provenance: { reason: 'Open unresolved question; inspect exact detail before any answer/replay.',
            originalDisposition: e.result ?? null,
            postedAt: e.at, batch: s.active?.events.includes(e.id) ? s.active.id : null,
            dispatcher: s.active?.events.includes(e.id) ? s.active.sessionID : null,
            health: s.active?.events.includes(e.id) ? s.active.health ?? 'awaiting-native-check' : 'unclaimed' } }) };
      // Every ID is represented; only individual summaries are bounded. Detail is lossless.
      entries.push({ id: e.id, at: e.at, ageMs: Math.max(0, this.now() - e.at), origin: e.origin,
        ref: e.ref, urgency: e.urgency, route: item.route, effect: item.effect,
        text: item.text.slice(0, 360), textOmittedChars: Math.max(0, item.text.length - 360),
        originalSummary: (e.text ?? '').slice(0, 240), detailEvent: e.id,
        ...(item.needsReconciliation ? { needsReconciliation: true, provenance: item.provenance } : {}) });
    }
    return JSON.stringify({ entries, total: pending.length, omitted: pending.length - entries.length });
  }
  async detail(event) {
    const rows = await this.rows(), original = state(rows).events.find(e => e.id === event);
    if (!original) throw Error('Unknown exact event ID');
    return { event: original, history: rows.filter(r => r.id === event && r.type === 'post' || r.event === event) };
  }
  async escalateUnanswered(send) {
    const due = state(await this.rows()).events.filter(e => !e.closed && e.urgency !== 'fyi'
      && this.now() >= e.at + unansweredEscalationMs).sort((a,b) => a.at - b.at);
    for (const event of due) {
      const admitted = await this.transaction(async (rows, append) => {
        const current = state(rows).events.find(e => e.id === event.id);
        if (!current || current.closed || rows.some(r => r.event === event.id
            && ['answer', 'chief-escalation-attempt'].includes(r.type))) return false;
        await append({ type: 'chief-escalation-attempt', event: event.id, at: this.now() });
        return true;
      });
      if (!admitted) continue;
      let status = 'admitted';
      try { await send(event); } catch { status = 'uncertain-no-replay'; }
      await this.transaction(async (_, append) => append({ type: 'chief-escalation-outcome', event: event.id, status, at: this.now() }));
    }
  }
  async recent({ max = 8, chars = 3000 } = {}) {
    const latest = new Map();
    for (const e of state(await this.rows()).events) latest.set(`${e.origin.sessionID}:${e.ref}`, e);
    const ordered = [...latest.values()].sort((a,b) => b.at - a.at), entries = [];
    for (const e of ordered) {
      const item = { id: e.id, at: e.at, origin: e.origin, ref: e.ref, urgency: e.urgency, route: e.result?.route, closed: Boolean(e.closed),
        excerpt: e.text.slice(0, 320), textOmittedChars: Math.max(0, e.text.length - 320),
        ...(e.result ? { filedSummary: e.result.text.slice(0, 240), summaryOmittedChars: Math.max(0, e.result.text.length - 240) } : {}) };
      if (entries.length === max || JSON.stringify({ entries: [...entries, item], omitted: ordered.length - entries.length - 1 }).length > chars) break;
      entries.push(item);
    }
    return JSON.stringify({ entries, omitted: ordered.length - entries.length });
  }
  close(event, text) {
    bounded(text, 4000, 'chief answer');
    return this.transaction(async (rows, append) => {
      const e = state(rows).events.find(e => e.id === event);
      if (!e?.result || e.result.route !== 'chief') throw Error('Only a chief inbox item can close');
      if (e.closed) return e.closed;
      const closed = { type: 'close', event, text, at: this.now() };
      await append(closed); return closed;
    });
  }
  reconcile(batch, note, { automatic = false, provenance = 'native-idle-confirmed' } = {}) {
    bounded(note, 2000, 'reconciliation note');
    return this.transaction(async (rows, append) => {
      const s = state(rows);
      if (s.active?.id !== batch) throw Error('Claim changed; refusing reconciliation');
      for (const id of s.active.events) {
        const original = s.events.find(e => e.id === id);
        if (!original?.result) {
          const uncertain = !automatic || rows.some(r => r.event === id && ['reply-attempt','nod-intent'].includes(r.type));
          await append({ type: 'result', event: id, route: 'chief', text: `Reconciliation required: ${note}`,
            effect: uncertain ? 'uncertain-no-replay' : 'no-effect-terminal-fallback', batch,
            ...(automatic ? { originalText: original.text } : {}), provenance: automatic ? provenance : 'chief-reconciled' });
        }
      }
      await append({ type: 'reconcile', batch, note, at: this.now() });
      await append({ type: 'finish', batch, at: this.now() });
    });
  }
  resolve({ sessionID, event, route, text, decision, quote }, { decisions }) {
    bounded(text, 4000, 'result text');
    if (!['chief', 'principal', 'covered', 'filed'].includes(route)) throw Error('Invalid route');
    // Accept old dispatcher schema input but queue NEW reserved needs for chief.
    // Do not rewrite historical results, Nod bindings, limits or uncertain effects.
    if (route === 'principal') route = 'chief';
    if (route === 'covered' && !Object.hasOwn(decisions, decision)) throw Error('Recorded standing decision required');
    if (route === 'covered') {
      quote ??= text; // Compatible exact-policy fixture callers; new tool explicitly supplies its supporting quote.
      bounded(quote, 4000, 'standing quote');
      if (!decisions[decision].includes(quote)) throw Error('Supporting quote must exactly match current standing policy');
    }
    // Persist the disposition BEFORE any adapter call. A timeout/crash never causes blind replay.
    return this.transaction(async (rows, append) => {
      const s = state(rows);
      if (!s.active || s.active.sessionID !== sessionID) throw Error('Dispatcher/origin boundary');
      const members = s.events.filter(e => s.active.events.includes(e.id));
      const matches = members.filter(e => e.id === event);
      // Compatibility for the observed mistaken business-ref call, ONLY inside
      // this child's exact bound batch. Never global lookup or fuzzy matching.
      const selected = matches.length ? matches : members.filter(e => e.ref === event);
      if (selected.length !== 1) throw Error('Use one exact action_handle from this bound batch; reference is absent/ambiguous (not a global event lookup)');
      const e = selected[0]; event = e.id;
      if (e.result) return e.result;
      const result = { type: 'result', event, route, text, ...(decision ? { decision } : {}), ...(quote ? { quote } : {}), effect: route === 'covered' ? 'reply-pending' : 'none' };
      await append(result);
      return result;
    });
  }
}
