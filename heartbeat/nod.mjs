import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { state } from './bus.mjs';
const canonical = value => Array.isArray(value) ? value.map(canonical) : value && typeof value === 'object'
  ? Object.fromEntries(Object.keys(value).sort().map(k => [k, canonical(value[k])])) : value;

// Existing installed chief-nod handles its own issuer auth. Never read/copy/print its token.
export function commandRun(command, args, input) {
  return new Promise((resolve, reject) => {
    const env = { ...process.env }; delete env.OPENCODE_SESSION_ID;
    const child = spawn(command[0], [...command.slice(1), ...args], { stdio: ['pipe', 'pipe', 'ignore'], env });
    let output = '', done = false;
    const finish = (error, result) => { if (done) return; done = true; clearTimeout(timer); error ? reject(error) : resolve(result); };
    const timer = setTimeout(() => { child.kill('SIGKILL'); finish(Error('Nod command timeout; outcome uncertain')); }, 25000);
    child.stdout.on('data', data => { output += data; if (output.length > 16000) { child.kill('SIGKILL'); finish(Error('Nod command output exceeded bound')); } });
    child.on('error', () => finish(Error('Nod command unavailable; reconcile attempt')));
    child.on('close', code => code === 0 ? finish(null, output) : finish(Error('Nod command failed; reconcile attempt')));
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify(input));
  });
}

export class NodAdapter {
  constructor(bus, { command, run = commandRun }) {
    if (!Array.isArray(command) || !path.isAbsolute(command[0])) throw Error('Explicit installed chief-nod command required');
    this.bus = bus; this.command = command; this.run = run;
  }
  async ask({ event, title, summary, limits, options, attention = false, recordRef }) {
    throw Error('New bus cards are disabled; queue the original item for chief judgment');
  }
  async check(requestID) {
    const rows = await this.bus.rows();
    if (!rows.some(r => r.type === 'nod-request' && r.mode === 'new-bus-only' && r.requestID === requestID)) throw Error('Only known new bus requests may be read');
    // This tiny read-only helper command is the documented kit integration change, not installed here.
    const answer = JSON.parse(await this.run(this.command, ['decision-json', requestID]));
    if (answer.request_id !== requestID) throw Error('Nod request identity mismatch');
    if (!answer.decision && !answer.decisions?.length) return { status: 'pending-not-consent' };
    return ingestNodAnswer(this.bus, { requestID, answer });
  }
}

// Operator/kit-only input, AFTER its existing authenticated Nod read. Not an unauthenticated callback/tool.
// It saves DATA and queues chief judgment on the SAME original event; never interprets a choice as authority.
export async function ingestNodAnswer(bus, { requestID, answer }) {
  if (!answer || typeof answer !== 'object' || Array.isArray(answer) || JSON.stringify(answer).length > 16000) throw Error('Invalid bounded Nod answer');
  if (answer.request_id !== requestID) throw Error('Nod request identity mismatch');
  const answerID = createHash('sha256').update(JSON.stringify(canonical(answer))).digest('hex');
  return bus.transaction(async (rows, append) => {
    const bindings = rows.filter(r => r.type === 'nod-request' && r.mode === 'new-bus-only' && r.requestID === requestID);
    if (bindings.length !== 1) throw Error('Not one exact opt-in bus request; legacy bindings unchanged');
    const binding = bindings[0];
    const e = state(rows).events.find(e => e.id === binding.event);
    if (!e || binding.origin?.sessionID !== e.origin?.sessionID || binding.origin?.directory !== e.origin?.directory)
      throw Error('Nod original event/origin binding mismatch');
    if (rows.some(r => r.type === 'nod-answer' && r.requestID === requestID && r.answerID === answerID)) return { status: 'duplicate' };
    if (!e || e.closed) throw Error('Original event closed/missing; changed answer needs explicit reconciliation');
    if (!answer.decision && !answer.decisions?.length) throw Error('No answer; pending/cancel/expiry is not consent');
    await append({ type: 'nod-answer', event: binding.event, requestID, answerID, origin: binding.origin, limits: binding.limits, answer, at: Date.now() });
    await append({ type: 'result', event: binding.event, route: 'chief', effect: 'none', text: `Saved Nod answer DATA for ${binding.ref}. Request ${requestID}, journal answer ${answerID}. Full original limits and exact answer are in that same journal answer row. Read them before judgment; partial/pending is not approval, hands are not completion. No automatic effects.` });
    return { status: 'queued-chief-no-effects', event: binding.event, answerID };
  });
}
