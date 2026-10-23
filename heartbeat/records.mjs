import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';

// Kit-owned continuation boundary only. This cannot fence host-owned result/goal paths.
export function appSessionReader(env = process.env, fetchImpl = fetch) {
  return async origin => {
    if (!env.OPENCHAMBER_AGENT_TOOL_URL || !env.OPENCHAMBER_AGENT_TOOL_TOKEN) throw Error('Authoritative app archive reader unavailable');
    const url = new URL(env.OPENCHAMBER_AGENT_TOOL_URL);
    if (!['127.0.0.1','[::1]','localhost'].includes(url.hostname)) throw Error('Local authenticated app runtime required');
    const response = await fetchImpl(url, {method:'POST',headers:{authorization:'Bearer '+env.OPENCHAMBER_AGENT_TOOL_TOKEN,'content-type':'application/json'},
      body:JSON.stringify({tool:'openchamber',sessionID:origin.sessionID,input:{action:'session.list',directory:origin.directory,all:true,limit:100}}),
      signal:AbortSignal.timeout(5000)});
    if (!response.ok) throw Error('Authoritative app archive read refused');
    const result = await response.json();
    if (result.ok !== true || !Array.isArray(result.data?.sessions)) throw Error('Authoritative app session list unavailable');
    const matches = result.data.sessions.filter(s=>s.id === origin.sessionID);
    if (matches.length !== 1) throw Error('Exact app session absent/ambiguous; no archive fallback');
    return matches[0];
  };
}

export function recipientEligibility({ rosterFile, session, readAppSession = appSessionReader() }) {
  return async origin => {
    if (!path.isAbsolute(rosterFile ?? '')) throw Error('Current enrolled roster is not bound');
    const response = await session.get({ sessionID: origin.sessionID }, { signal: AbortSignal.timeout(5000) });
    const native = response.data ?? response;
    if (native?.id !== origin.sessionID || native.agent !== 'lead' || native.time?.archived
        || native.location?.directory !== origin.directory) throw Error('Original native recipient moved/archived/mismatched');
    const rows = (await readFile(rosterFile,'utf8')).split('\n').filter(s=>s.trim()).map(s=>JSON.parse(s));
    const own = rows.filter(r=>r.session === origin.sessionID);
    if (own.length !== 1 || own[0].directory !== origin.directory || own[0].state !== 'active')
      throw Error('Original recipient roster held/archived/ineligible');
    const app = await readAppSession(origin);
    if (app?.id !== origin.sessionID || app.location?.directory !== origin.directory || !app.time
        || app.time.archived !== undefined && app.time.archived !== null)
      throw Error('Authoritative app recipient archived/moved/unknown');
    return {sessionID:origin.sessionID,directory:origin.directory,held:false,archived:false};
  };
}

// Bind explicit sections of the existing project records, not a second hold ledger.
export function projectHolds(bindings = {}) {
  return async origin => {
    const configured = bindings[origin.directory];
    const sources = Array.isArray(configured) ? configured : configured?.lanes?.[origin.lane]
      ? [...(configured.global ?? []), ...configured.lanes[origin.lane]] : undefined;
    if (!Array.isArray(sources) || !sources.length) throw Error('Current project hold records are not bound');
    const evidence = [];
    for (const { file, heading, allowedQuote, clearQuote } of sources) {
      const expected = allowedQuote ?? clearQuote; // Legacy fixture alias; this is lane permission, not an invented all-clear.
      if (!path.isAbsolute(file) || typeof heading !== 'string' || !heading.startsWith('#') || !expected?.trim()) throw Error('Invalid hold record binding');
      const text = await readFile(file, 'utf8'), lines = text.split(/\r?\n/), start = lines.indexOf(heading);
      if (start < 0) throw Error('Hold section missing; refusing resume');
      const level = heading.match(/^#+/)[0].length;
      let end = start + 1;
      while (end < lines.length && !(new RegExp(`^#{1,${level}} `)).test(lines[end])) end++;
      const section = lines.slice(start + 1, end).join('\n').trim();
      if (section !== expected.trim()) throw Error('Project hold state is not the explicitly recorded clear/allowed state for this wait lane');
      evidence.push({ file, heading, digest: createHash('sha256').update(section).digest('hex') });
    }
    return evidence;
  };
}

export async function standingPolicy(options) {
  let instructions = options.chiefInstructionsFile ? await readFile(options.chiefInstructionsFile, 'utf8') : options.chiefInstructions;
  // Installed agent frontmatter is enforced metadata, NOT prose to smuggle into a dispatcher prompt.
  if (instructions?.startsWith('---\n')) instructions = instructions.split('\n---\n').slice(1).join('\n---\n').trim();
  let decisions = options.decisionsFile ? JSON.parse(await readFile(options.decisionsFile, 'utf8')) : options.decisions;
  const sources = [];
  if (options.standingSections || options.standingFiles) {
    decisions = {};
    for (const spec of options.standingSections ?? options.standingFiles.map(file => ({ file }))) {
      if (!path.isAbsolute(spec.file ?? '')) throw Error('Absolute existing standing source required');
      const full = await readFile(spec.file, 'utf8'), body = spec.heading ? section(full, spec.heading) : full;
      const ref = spec.heading ? `${spec.file}#${spec.heading}` : spec.file, paragraphs = body.split(/\n\s*\n/).filter(Boolean);
      let selected = '', included = 0;
      const cap = Math.max(128, Math.min(spec.maxChars ?? 3000, 4000));
      for (const paragraph of paragraphs) {
        const next = selected ? selected + '\n\n' + paragraph : paragraph;
        if (next.length > cap || JSON.stringify({ ...decisions, [ref]: next }).length > 12000) break;
        selected = next; included++;
      }
      if (selected) decisions[ref] = selected;
      sources.push({ ref, file: spec.file, heading: spec.heading, includedParagraphs: included, omittedParagraphs: paragraphs.length - included });
    }
  }
  if (typeof instructions !== 'string' || instructions.length > 20000 || !decisions || JSON.stringify(decisions).length > 20000) throw Error('Instructions/standing files missing or exceed candidate budget');
  return { instructions, decisions, sources };
}
function section(text, heading) {
  const lines = text.split(/\r?\n/), start = lines.indexOf(heading);
  if (start < 0 || !/^#+ /.test(heading)) throw Error('Configured standing section missing');
  const level = heading.match(/^#+/)[0].length; let end = start + 1;
  while (end < lines.length && !new RegExp(`^#{1,${level}} `).test(lines[end])) end++;
  return lines.slice(start + 1, end).join('\n').trim();
}
