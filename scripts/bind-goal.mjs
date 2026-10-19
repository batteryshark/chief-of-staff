#!/usr/bin/env node
// Explicit operator setup only. GET system info, never control/create/auth/start.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {privatePath,validateOrigin,validateAuth,serverIdentity,requestJson} from '../hosts/domain-policy/goal-binding.mjs';

export async function bindGoal(options,{fetchImpl=fetch}={}) {
  try {
    const allowed=['home','lead-agent','binding','origin','auth-file','desktop-settings'];
    if (Object.keys(options).some(k=>!allowed.includes(k)) || Boolean(options['auth-file'])===Boolean(options['desktop-settings'])) throw Error();
    const home=fs.realpathSync(options.home),file=options.binding,lead=options['lead-agent'];
    if (!/^[a-z][a-z0-9-]{0,47}$/.test(lead||'') || !path.isAbsolute(file) || path.resolve(file)!==file || file.startsWith(home+path.sep)) throw Error();
    privatePath(path.dirname(file),true);
    const origin=validateOrigin(options.origin);
    const source=JSON.parse(fs.readFileSync(privatePath(options['auth-file']||options['desktop-settings']),'utf8'));
    const auth=options['auth-file'] ? validateAuth(source) : validateAuth({Authorization:'Bearer '+source.desktopLocalClientToken});
    if (options['desktop-settings'] && source.desktopLocalPort!==Number(new URL(origin).port)) throw Error();
    const server=serverIdentity(await requestJson(origin,auth,'/api/system/info',undefined,fetchImpl));
    if (server.port!==Number(new URL(origin).port)) throw Error();
    const fd=fs.openSync(file,'wx',0o600);
    try { fs.writeFileSync(fd,JSON.stringify({version:1,home,lead_agent:lead,origin,auth,server})+'\n');fs.fsyncSync(fd); }
    finally { fs.closeSync(fd); }
    return 'Operator binding saved. Native caller, goal creation and wakeups are NOT yet tested.';
  } catch { throw Error('Binding setup refused; check private paths, explicit origin, existing authentication and running server. No control request was sent.'); }
}
if (process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try {
    const args=process.argv.slice(2),options={};
    if (args.length%2) throw Error();
    for (let i=0;i<args.length;i+=2) {
      if (!args[i].startsWith('--') || options[args[i].slice(2)]!==undefined) throw Error();
      options[args[i].slice(2)]=args[i+1];
    }
    console.log(await bindGoal(options));
  } catch { console.error('Goal binding setup failed; no credentials or server response logged.');process.exitCode=1; }
}
