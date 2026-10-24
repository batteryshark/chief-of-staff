// Installed entry: no argv/config/state overrides and no model/HTTP calls.
// norman: machine-only JSON protocol, add human help only if exposed as an interactive command.
import { open } from 'node:fs/promises';
import { constants } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { Bus } from './bus.mjs';
import { requestOK, snapshot } from './question-status.mjs';
const timer = setTimeout(()=>process.exit(1), 4900);
try {
  if (process.argv.length !== 2) throw Error();
  let input = '';
  for await (const chunk of process.stdin) {
    input += chunk;
    if (Buffer.byteLength(input) > 4096) throw Error();
  }
  const q = JSON.parse(input);
  if (!requestOK(q)) throw Error();
  let bus, coverage;
  try {
    const file = await open(path.join(os.homedir(), '.chief-of-staff/heartbeat/pilot-options.json'), constants.O_RDONLY | constants.O_NOFOLLOW);
    let options;
    try {
      const stat = await file.stat();
      if (!stat.isFile() || stat.uid !== process.getuid() || stat.mode & 0o022 || stat.size > 524288) throw Error();
      options = JSON.parse(await file.readFile('utf8'));
    } finally { await file.close(); }
    bus = new Bus(options.memoryRoot); coverage = options.questionCoverage;
  } catch { bus = {inbox:async()=>{throw Error();}}; }
  const out = await snapshot(bus, q, coverage);
  process.stdout.write(JSON.stringify(out)+'\n');
} catch { process.exitCode = 1; }
finally { clearTimeout(timer); }
