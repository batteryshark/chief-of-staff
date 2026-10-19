// Unary native SDK: observation only. No promise here claims RPC cancellation.
import {AsyncLocalStorage} from 'node:async_hooks';

export function boundary({callMs=4000,turnMs=60000,cap=4}={}) {
  const local=new AsyncLocalStorage(), stop=new AbortController(), pending=new Set();
  const failure=()=>Error('native observation abandoned; outcome unknown; reconcile exact owned IDs');
  function check() {
    const turn=local.getStore();
    if (!turn || stop.signal.aborted || turn.signal.aborted) throw failure();
  }
  async function observe(fn, ms=callMs) {
    check();
    if (pending.size>=cap) throw Error('native unresolved call cap; admission refused');
    const turn=local.getStore();
    let timer, abort;
    // Attach BOTH settlement handlers immediately, including after abandonment.
    const token={};pending.add(token);
    const work=Promise.resolve().then(()=>{check();return fn();});
    const settled=work.then(value=>{pending.delete(token);return value;},error=>{pending.delete(token);throw error;});
    try {
      const abandoned=new Promise((_,reject)=>{
        abort=()=>reject(failure());
        turn.signal.addEventListener('abort',abort,{once:true});
        timer=setTimeout(()=>turn.abort(),ms);
        if (turn.signal.aborted) abort();
      });
      const value=await Promise.race([settled,abandoned]);
      check();return value;
    } finally {
      clearTimeout(timer);turn.signal.removeEventListener('abort',abort);
    }
  }
  async function run(fn, signal) {
    if (stop.signal.aborted || signal?.aborted || pending.size) throw failure();
    const controller=new AbortController();
    const abort=()=>controller.abort();
    const turn={signal:controller.signal,abort};
    stop.signal.addEventListener('abort',abort,{once:true});
    signal?.addEventListener('abort',abort,{once:true});
    const timer=setTimeout(abort,turnMs);
    try { return await local.run(turn,async()=>{check();const v=await fn();check();return v;}); }
    finally {
      abort();clearTimeout(timer);
      stop.signal.removeEventListener('abort',abort);signal?.removeEventListener('abort',abort);
    }
  }
  return {run,observe,check,stop:()=>stop.abort(),get stopped(){return stop.signal.aborted;},
    get unresolved(){return pending.size;}};
}
