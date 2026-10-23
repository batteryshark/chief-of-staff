// Private local JSONL sink candidate. No hooks, daemon, retries or permission effects.
import { constants } from 'node:fs';
import { open, lstat, realpath } from 'node:fs/promises';
import path from 'node:path';

// Serialized fallback drops action/rules, so its observation ID differs. The SAME
// native call must still deduplicate. Missing correlation never fabricates equality.
const key = row => row.source?.session && row.source?.message && row.source?.call
  ? JSON.stringify([row.source.session,row.source.message,row.source.call]) : row.id;

export async function denialLog(file) {
  const parent=path.dirname(file),stat=await lstat(parent);
  if (!path.isAbsolute(file) || stat.isSymbolicLink() || !stat.isDirectory()
      || stat.uid!==process.getuid() || (stat.mode&0o077)!==0 || await realpath(parent)!==parent)
    throw Error('Private canonical owned log directory required');
  const fd=await open(file,constants.O_CREAT|constants.O_RDWR|constants.O_APPEND|constants.O_NOFOLLOW,0o600);
  let seen;
  try {
    const info=await fd.stat();
    if (!info.isFile() || info.uid!==process.getuid() || (info.mode&0o077)!==0 || info.size>1024*1024)
      throw Error('Unsafe or oversized log refused');
    seen=new Set((await fd.readFile('utf8')).split('\n').filter(Boolean).map(line=>key(JSON.parse(line))));
  } catch (error) {try {await fd.close();} catch {} throw error;}
  let pending=Promise.resolve(),closed=false,writeUncertain=false;
  return {
    status:()=>({available:!closed&&!writeUncertain,state:closed?'closed':writeUncertain?'write-uncertain-inspection-required':'ready'}),
    append(record) {
      const task=pending.then(async()=>{
        if (closed) throw Error('Log closed');
        if (writeUncertain) throw Error('Log write outcome uncertain; reopen after inspection');
        if (record?.type!=='permission-denial' || !/^[a-f0-9]{64}$/.test(record.id)) throw Error('Sanitized observation required');
        if (seen.has(key(record))) return {status:'duplicate'};
        const line=JSON.stringify(record)+'\n';
        if (Buffer.byteLength(line)>16384 || (await fd.stat()).size+Buffer.byteLength(line)>1024*1024) throw Error('Log bound exceeded');
        // Rejected append/sync may already have written bytes. Park rather than
        // retry, append onto partial JSON, or claim an unconfirmed durable result.
        try {await fd.appendFile(line);await fd.sync();}
        catch (error) {writeUncertain=true;throw error;}
        seen.add(key(record));
        return {status:'appended'};
      });
      pending=task.catch(()=>{});return task;
    },
    async close() { await pending;closed=true;await fd.close(); },
  };
}
