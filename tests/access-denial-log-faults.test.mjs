// Independent risk regressions adopted against CURRENT kit source, not frozen copies.
// Only this import's fs boundary is replaced; no native hooks or actual disk failures.
import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';

let fixture;
const url=new URL('../access/denial-log.mjs?storage-faults',import.meta.url).href;
globalThis.__accessDenialFaultFS={open:async()=>fixture.fd,lstat:async()=>fixture.stat,realpath:async p=>p};
const hooks=registerHooks({resolve(specifier,context,next){
  if(specifier==='node:fs/promises' && context.parentURL===url)
    return {url:'data:text/javascript,export const {open,lstat,realpath}=globalThis.__accessDenialFaultFS;',shortCircuit:true};
  return next(specifier,context);
}});
let denialLog;
try {({denialLog}=await import(url));} finally {hooks.deregister();delete globalThis.__accessDenialFaultFS;}

function filesystem({syncFail=false,appendPartial=false,read='',statError=false,readError=false,closeError=false}={}) {
  let bytes=read,closes=0,writes=0,syncs=0;
  const stat={isSymbolicLink:()=>false,isDirectory:()=>true,uid:process.getuid(),mode:0o700};
  const fd={
    async stat(){if(statError)throw Error('synthetic stat failure');return {isFile:()=>true,uid:process.getuid(),mode:0o600,size:Buffer.byteLength(bytes)};},
    async readFile(){if(readError)throw Error('synthetic read failure');return bytes;},
    async appendFile(line){writes++;if(appendPartial){bytes+=line.slice(0,12);throw Error('synthetic partial append');}bytes+=line;},
    async sync(){syncs++;if(syncFail)throw Error('synthetic fsync failure');},
    async close(){closes++;if(closeError)throw Error('synthetic close failure');},
  };
  return {stat,fd,metrics:()=>({bytes,closes,writes,syncs})};
}
const record={type:'permission-denial',id:'a'.repeat(64),source:{session:'ses_A',message:'msg_A',call:'call_A'}};

test('successful append followed by fsync failure parks logging without duplicate retry writes',async()=>{
  fixture=filesystem({syncFail:true});const log=await denialLog('/synthetic/private/log.jsonl');
  try {
    await assert.rejects(log.append(record),/synthetic fsync failure/);
    assert.deepEqual(log.status(),{available:false,state:'write-uncertain-inspection-required'});
    await assert.rejects(log.append(record),/outcome uncertain/);
    await assert.rejects(log.append({...record,id:'b'.repeat(64),source:{...record.source,call:'call_B'}}),/outcome uncertain/);
    assert.equal(fixture.metrics().bytes.trim().split('\n').length,1);
    assert.equal(fixture.metrics().writes,1);assert.equal(fixture.metrics().syncs,1);
  } finally {await log.close();}
  assert.equal(fixture.metrics().closes,1);assert.equal(log.status().available,false);
});

test('partial append parks queued and subsequent writes rather than corrupting JSON further',async()=>{
  fixture=filesystem({appendPartial:true});const log=await denialLog('/synthetic/private/log.jsonl');
  try {
    const results=await Promise.allSettled([log.append(record),log.append(record)]);
    assert.equal(results[0].status,'rejected');assert.match(results[0].reason.message,/partial append/);
    assert.equal(results[1].status,'rejected');assert.match(results[1].reason.message,/outcome uncertain/);
    const before=fixture.metrics().bytes;
    await assert.rejects(log.append(record),/outcome uncertain/);
    assert.equal(fixture.metrics().bytes,before);assert.equal(fixture.metrics().writes,1);
    assert.equal(log.status().available,false);
  } finally {await log.close();}
  assert.equal(fixture.metrics().closes,1);
});

test('parse/stat/read initialization failures close descriptor and preserve original exception',async()=>{
  for(const [options,expected] of [[{read:'{"truncated":'},SyntaxError],[{statError:true},/stat failure/],
    [{readError:true},/read failure/],[{readError:true,closeError:true},/read failure/]]) {
    fixture=filesystem(options);
    await assert.rejects(denialLog('/synthetic/private/log.jsonl'),expected);
    assert.equal(fixture.metrics().closes,1);assert.equal(fixture.metrics().writes,0);
  }
});
