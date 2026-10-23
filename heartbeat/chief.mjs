import { readFile } from 'node:fs/promises';
import path from 'node:path';

export function chiefSelection(options, ctx) {
  const read = async () => {
    const pointer = options.fixtureMode === true
      ? { session: options.chiefSessionID, directory: options.chiefDirectory ?? ctx.location?.directory }
      : JSON.parse(await readFile(requiredPath(options.chiefPointerFile), 'utf8'));
    if (typeof pointer?.session !== 'string' || !pointer.session.startsWith('ses_') || pointer.session.length > 256 || !path.isAbsolute(pointer?.directory ?? '')) throw Error('Invalid current chief pointer binding');
    return { session: pointer.session, directory: path.resolve(pointer.directory) };
  };
  const current = async () => {
    const binding = await read(), response = await ctx.session.get({ sessionID: binding.session }), session = response.data ?? response;
    const actual = session?.location?.directory;
    if (!session || !path.isAbsolute(actual ?? '') || (session.id !== binding.session && !(options.fixtureMode === true && !session.id)) || session.time?.archived || path.resolve(actual) !== binding.directory) throw Error('Chief pointer does not match a valid native session/directory');
    return binding;
  };
  const authorized = async sessionID => (await read()).session === sessionID && (await current()).session === sessionID;
  return { read, current, authorized };
}
const requiredPath = file => { if (!path.isAbsolute(file ?? '')) throw Error('Explicit existing chief.json path required (or fixtureMode override)'); return file; };
