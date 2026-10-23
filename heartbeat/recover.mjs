// Operator CLI. Exact configured bus only; no automatic recovery or session interruption.
import { Bus } from './bus.mjs';
import { readFile } from 'node:fs/promises';
const [flag, file, action, inode, ...note] = process.argv.slice(2);
if (flag !== '--options' || !file?.startsWith('/')) throw Error('Use --options /absolute/known/heartbeat-options.json status (no config guessing)');
const o = JSON.parse(await readFile(file, 'utf8'));
if (!o?.memoryRoot) throw Error('Expected explicit heartbeat options file');
const bus = new Bus(o.memoryRoot);
if (action === 'status') console.log(JSON.stringify(await bus.status(), null, 2));
else if (action === 'unlock-confirmed-no-writer') {
  if (!note.length || !/^\d+$/.test(inode ?? '')) throw Error('Usage: unlock-confirmed-no-writer INODE reconciliation-note');
  await bus.recoverLock({ inode: Number(inode), noWriterConfirmed: true, note: note.join(' ') });
  console.log('Exact lock removed after explicit operator reconciliation; no events replayed.');
} else throw Error('Use status. Only after independently confirming no active writer: unlock-confirmed-no-writer INODE NOTE.');
