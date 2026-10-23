import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
export const pairedMetadata = source => (sessionID, directory, patch) => new Promise((resolve, reject) => {
  const child = spawn('python3', ['-B', fileURLToPath(new URL('./paired-app.py', import.meta.url)), source], { stdio: ['pipe','pipe','ignore'] });
  let output = '', done = false;
  const finish = (error, value) => { if (done) return; done = true; clearTimeout(timer); error ? reject(error) : resolve(value); };
  const timer = setTimeout(() => { child.kill('SIGKILL'); finish(Error('Paired metadata timeout')); }, 12000);
  child.stdout.on('data', chunk => { output += chunk; if (output.length > 32000) { child.kill('SIGKILL'); finish(Error('Paired metadata bound')); } });
  child.on('error', () => finish(Error('Paired metadata client unavailable')));
  child.on('close', code => { try { if (code !== 0) throw Error(); finish(null, JSON.parse(output)); } catch { finish(Error('Paired metadata refused; no fallback')); } });
  child.stdin.on('error', () => {});
  child.stdin.end(JSON.stringify({ sessionID, directory, ...(patch ? { patch } : {}) }));
});
