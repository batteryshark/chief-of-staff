// One private fixed Python child at a time, no shell/inherited auth environment.
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import fs from 'node:fs';

const SCRIPT = fileURLToPath(new URL('../../scripts/desk_native_bridge.py', import.meta.url));
const MAX = 262144;
export function bridge({home, python}) {
  // Operator supplies an exact absolute interpreter, never a model argument/PATH lookup.
  if (!python?.startsWith('/') || !fs.statSync(python).isFile()) throw Error('fixed Python interpreter required');
  let busy = false;
  return async (op, args = {}) => {
    if (busy) throw Error('host bridge busy; bounded admission refused');
    const input = JSON.stringify({home, op, args});
    if (Buffer.byteLength(input) > MAX) throw Error('host request exceeds bound');
    busy = true;
    try {
      return await new Promise((resolve, reject) => {
        const child = spawn(python, ['-I', '-B', SCRIPT], {
          shell: false, stdio: ['pipe', 'pipe', 'pipe'], cwd: home,
          env: {PATH: '/usr/bin:/bin', LANG: 'en_US.UTF-8', PYTHONNOUSERSITE: '1'},
        });
        let output = '', size = 0, failed = false;
        const fail = () => { failed = true; child.kill('SIGKILL'); };
        const timer = setTimeout(fail, 5000);
        child.stdout.on('data', b => { size += b.length; if (size > MAX) fail(); else output += b; });
        // Drain bounded stderr without retaining secrets/traceback.
        child.stderr.on('data', b => { size += b.length; if (size > MAX) fail(); });
        child.stdin.on('error', () => { failed = true; });
        child.on('error', () => { failed = true; });
        child.on('close', code => {
          clearTimeout(timer);
          try {
            const v = JSON.parse(output);
            if (failed || code !== 0 || v.ok !== true) throw Error();
            resolve(v.data);
          } catch { reject(Error('private bridge failed; no replay, reconcile owned state')); }
        });
        child.stdin.end(input);
      });
    } finally { busy = false; }
  };
}
