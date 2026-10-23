// OpenChamber app metadata control, NOT native OpenCode metadata storage.
import { docketBinding } from './timed-wait.mjs';
import { resolvedObjective } from './objective.mjs';
export function appMetadata(env = process.env) {
  if (!env.OPENCHAMBER_AGENT_TOOL_URL || !env.OPENCHAMBER_AGENT_TOOL_TOKEN) throw Error('Inherited OpenChamber runtime access unavailable');
  return async (sessionID, directory, patch) => {
    const u = new URL(env.OPENCHAMBER_AGENT_TOOL_URL);
    if (!['127.0.0.1', '[::1]', 'localhost'].includes(u.hostname)) throw Error('Local app runtime required');
    u.pathname = `/api/openchamber/sessions/${encodeURIComponent(sessionID)}/metadata`;
    if (!patch) u.searchParams.set('directory', directory);
    const r = await fetch(u, { method: patch ? 'POST' : 'GET', headers: { authorization: `Bearer ${env.OPENCHAMBER_AGENT_TOOL_TOKEN}`, 'content-type': 'application/json' },
      ...(patch ? { body: JSON.stringify({ directory, patch }) } : {}), signal: AbortSignal.timeout(5000) });
    if (!r.ok) throw Error(`OpenChamber metadata ${r.status}`);
    return (await r.json()).metadata;
  };
}

export class GoalWait {
  constructor(bus, { metadata = appMetadata(), allowedSessions = [], goalBindings = {}, prompt, readDocket, messages, checkRecipient = async () => { throw Error('Recipient eligibility not bound'); }, checkHolds = async () => { throw Error('Project hold records not bound'); }, now = Date.now }) {
    Object.assign(this, { bus, metadata, allowedSessions, goalBindings, prompt, checkHolds, checkRecipient, now, readDocket, messages });
  }
  async pauseDocket(itemID, origin) {
    if (!this.allowedSessions.includes(origin.sessionID)) throw Error('Goal wait not enabled for this origin');
    if (!this.readDocket) throw Error('Docket binding unavailable');
    const item = await this.readDocket(itemID), docket = docketBinding(item, origin, this.now());
    if (docket.id !== itemID) throw Error('Docket ID mismatch');
    return this.pause(`docket:${itemID}`, origin, docket);
  }
  async resumeDocket(itemID, origin) {
    if (!this.allowedSessions.includes(origin.sessionID)) throw Error('Goal wait not enabled for this origin');
    if (!this.readDocket || !this.messages) throw Error('Docket read/context binding unavailable');
    const item = await this.readDocket(itemID), docket = docketBinding(item, origin, this.now(), true), aid = item.receipt?.admission_id;
    const wait = (await this.bus.rows()).find(r => r.type === 'goal-wait' && r.event === `docket:${itemID}`);
    if (docket.id !== itemID || !wait?.docket || wait.origin.sessionID !== origin.sessionID || wait.origin.directory !== origin.directory || JSON.stringify(wait.docket) !== JSON.stringify(docket)) throw Error('No matching own timed wait');
    const messages = await this.messages(origin.sessionID);
    if (!aid || !Array.isArray(messages) || !messages.some(m => m.id === aid && m.type === 'user')) throw Error('Genuine Docket admission not present in this session context');
    // Explicit lead-owned tool call after interpreting wake; never triggered by arbitrary incoming text.
    return this.wake(`docket:${itemID}`, '', { docket: true, admissionID: aid });
  }
  async pause(event, origin, docket) {
    if (!this.allowedSessions.includes(origin.sessionID)) throw Error('Goal wait not enabled for this origin');
    return this.bus.transaction(async (rows, append) => {
      const posted = rows.find(r => r.type === 'post' && r.id === event);
      if (!docket && (!posted || posted.origin.sessionID !== origin.sessionID || posted.origin.directory !== origin.directory)) throw Error('Wait origin/event mismatch');
      if (rows.some(r => ['answer', 'close'].includes(r.type) && r.event === event)) throw Error('Event already answered/closed; refusing a new wait');
      const prior = rows.find(r => r.type === 'goal-wait' && r.event === event);
      if (prior) return { ...prior, status: rows.some(r => r.type === 'goal-paused' && r.event === event) ? 'paused-confirmed' : 'unconfirmed-reconcile' };
      await this.checkRecipient(origin);
      const holds = await this.checkHolds(origin);
      const metadata = await this.metadata(origin.sessionID, origin.directory);
      const goal = metadata?.openchamber?.goal;
      if (!goal?.id || goal.status !== 'active') throw Error('Only own active goal may wait; never override stop/hold');
      const binding = this.goalBindings[origin.sessionID];
      if (binding && (goal.id !== binding.id || goal.objective !== binding.objective || Boolean(goal.objectiveFile) !== binding.objectiveFile)) throw Error('Goal differs from reviewed scope binding');
      const effective = await resolvedObjective(goal, origin.sessionID, binding);
      const at = this.now(), reason = `heartbeat-wait:${event}`;
      const wait = { type: 'goal-wait', event, origin, ...(docket ? { docket } : {}), goalID: goal.id,
        inlineObjective: goal.objective, objective: effective.text, objectiveSource: effective.source,
        effectiveObjectiveSha256: effective.sha256, objectiveFile: Boolean(goal.objectiveFile), tokenBudget: goal.tokenBudget, holds, at, reason };
      // Attempt before effect: an ambiguous failure must be reconciled, not replayed.
      await append(wait);
      await this.metadata(origin.sessionID, origin.directory, { openchamber: { goal: { status: 'paused', statusReason: reason, updatedAt: at } } });
      await append({ type: 'goal-paused', event, at });
      return { ...wait, status: 'paused-confirmed' };
    });
  }
  async wake(event, text, resume = {}) {
    return this.bus.transaction(async (rows, append) => {
      const wait = rows.find(r => r.type === 'goal-wait' && r.event === event);
      if (!wait) return { status: 'no-goal-wait' };
      if (rows.some(r => r.type === 'chief-record-close' && r.event === event)) throw Error('Chief record-only close forbids resume');
      if (Boolean(wait.docket) !== Boolean(resume.docket)) throw Error('Timed/bus resume binding mismatch');
      if (rows.some(r => r.type === 'goal-wake-attempt' && r.event === event)) return { status: 'already-attempted-no-replay' };
      if (rows.some(r => r.type === 'close' && r.event === event && r.reason !== 'chief-answer-recorded')) throw Error('Event already closed; refusing resume');
      if (!wait.docket && rows.some(r=>r.type==='answer' && r.event===event && r.text!==text)) throw Error('Recorded answer mismatch');
      if (!rows.some(r => r.type === 'goal-paused' && r.event === event) || !this.allowedSessions.includes(wait.origin.sessionID)) throw Error('Unconfirmed wait; reconcile');
      const { origin } = wait;
      await this.checkRecipient(origin);
      const holds = await this.checkHolds(origin);
      if (!wait.holds || JSON.stringify(holds) !== JSON.stringify(wait.holds)) throw Error('Project hold record changed; refusing resume');
      // Read the goal last, immediately before the resume intent/write. This is NOT host CAS.
      const metadata = await this.metadata(origin.sessionID, origin.directory), goal = metadata?.openchamber?.goal;
      if (!matches(goal, wait)) throw Error('Goal changed/manual stop or hold; refusing resume');
      const effective = await resolvedObjective(goal, origin.sessionID, this.goalBindings[origin.sessionID]);
      if (effective.sha256 !== wait.effectiveObjectiveSha256 || effective.source !== wait.objectiveSource) throw Error('Resolved goal objective changed; refusing resume');
      await append({ type: 'goal-wake-attempt', event, at: this.now() });
      // Durable intent can itself take time. Recheck after it, as close to the POST as the API permits.
      if (JSON.stringify(await this.checkHolds(origin)) !== JSON.stringify(wait.holds)) throw Error('Project hold record changed; refusing resume');
      const fresh = (await this.metadata(origin.sessionID, origin.directory))?.openchamber?.goal;
      if (!matches(fresh, wait)) throw Error('Goal changed/manual stop or hold; refusing resume');
      const finalObjective = await resolvedObjective(fresh, origin.sessionID, this.goalBindings[origin.sessionID]);
      if (finalObjective.sha256 !== wait.effectiveObjectiveSha256 || finalObjective.source !== wait.objectiveSource) throw Error('Resolved goal objective changed before resume');
      // Preserve objective, budget, counters and all other metadata. No abort of active/nested work.
      await this.checkRecipient(origin);
      await this.metadata(origin.sessionID, origin.directory, { openchamber: { goal: { status: 'active', statusReason: 'resumed', updatedAt: this.now() } } });
      // Genuine matching bus answer, no extra fabricated spinner. Admission is not owner completion.
      if (!wait.docket) await this.prompt({ sessionID: origin.sessionID, text: `Heartbeat answer for ${postedRef(rows, event)}: ${text}`, delivery: 'queue' });
      await append({ type: 'goal-woken', event, ...(resume.admissionID ? { admissionID: resume.admissionID } : {}), at: this.now() });
      return { status: wait.docket ? 'resumed-in-current-docket-turn' : 'resumed-answer-admitted' };
    });
  }
}
const postedRef = (rows, id) => rows.find(r => r.type === 'post' && r.id === id)?.ref ?? id;
const matches = (goal, wait) => goal?.id === wait.goalID && goal.status === 'paused' && goal.statusReason === wait.reason && goal.updatedAt === wait.at && goal.objective === (wait.inlineObjective ?? wait.objective) && Boolean(goal.objectiveFile) === Boolean(wait.objectiveFile) && goal.tokenBudget === wait.tokenBudget;
