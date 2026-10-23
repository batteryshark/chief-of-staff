import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {z} from 'zod';
import {dispatchNative,nativeDispatchAdvice} from './host-dispatch.mjs';

export function serverFromArgv(argv=process.argv) {
  let port;
  for(let i=0;i<argv.length;i++) {
    if(argv[i]==='--port') port=argv[i+1];
    if(argv[i].startsWith('--port=')) port=argv[i].slice(7);
  }
  return /^\d+$/.test(port||'') && +port>0 && +port<=65535 ? `http://127.0.0.1:${port}` : undefined;
}

export function invoke(request, {server=serverFromArgv(), signal, executable=process.env.CHIEF_RUNWAY_PYTHON||'python3', entry=fileURLToPath(new URL('./runway_main.py',import.meta.url))}={}) {
  return new Promise((resolve,reject)=>{
    const child=spawn(executable,['-B',entry,...(server?['--server',server]:[]),...(process.env.CHIEF_RUNWAY_TARMAC_URL?['--tarmac',process.env.CHIEF_RUNWAY_TARMAC_URL]:[])],{stdio:['pipe','pipe','pipe'],signal});
    let output='',error='';
    const timer=setTimeout(()=>child.kill('SIGTERM'),25000);
    child.stdout.on('data',x=>{output+=x;if(output.length>2_000_000)child.kill('SIGTERM');});
    child.stderr.on('data',x=>{error+=x;if(error.length>8000)error=error.slice(-8000);});
    child.on('error',e=>{clearTimeout(timer);reject(e);});
    // status and usage answer in plain text (a short table); everything else is compact JSON.
    child.on('close',code=>{clearTimeout(timer);try{resolve(JSON.parse(output));}catch{if(code===0&&output.trim())resolve({text:output.trim()});else reject(new Error('Runway helper did not return a result; check the installation.'));}});
    child.stdin.on('error',()=>{});
    child.stdin.end(JSON.stringify(request));
  });
}

export default {
  id:'chief-runway',
  async setup(ctx) {
    await ctx.tool.transform(editor=>editor.add({
      name:'runway', options:{codemode:false},
       description:'Chief-of-staff quota routing and durable worker ledger. Read the installed routing/WORKFLOW.md before first use. status shows a short usage table, open attempts and routes; usage lists allowances that would go unspent at their reset (burn) and ones nearly gone (low), so read it before dispatching new work; plan chooses a suitable model; prepare reserves admission and returns dispatch args; bind records the returned session; finish verifies idle state and saves completion/checkpoints. plan and prepare prefer burnable allowances automatically. prefer requires a user request and expires at its observed reset. Only explicit policy-bound dispatch launches a fresh worker. No global model/goal changes, purchases or reset redemption.',
       input:z.object({request:z.string().describe('JSON request with action: status, usage, plan, prepare, prefer, clear-preference, bind, finish, report-failure, dispatch or collect-dispatch. plan/prepare accept exclude_routes. Add "format":"json" only when raw data is truly needed. See WORKFLOW.md for required fields.')}),
      async execute({request},c) {
        const req=JSON.parse(request);
        if(!req || typeof req!=='object' || Array.isArray(req))throw new Error('Request must be an object');
        if (['dispatch','collect-dispatch'].includes(req.action)) {
          const fields=req.action==='dispatch'?['action','attempt','prompt']:['action','attempt'];
          if (Object.keys(req).some(k=>!fields.includes(k))) throw Error('Dispatch accepts only attempt/prompt; native origin/selection are not agent inputs');
          return {content:JSON.stringify(await dispatchNative(ctx,c,req,invoke))};
        }
        if (req.action?.startsWith('dispatch-')) throw Error('Internal dispatch record actions are not agent inputs');
        if(!req.scope)req.scope=ctx.location.project.canonical||ctx.location.directory;
        if(req.task)req.task={...req.task,scope:req.task.scope||req.scope,directory:req.task.directory||ctx.location.directory};
        const result=nativeDispatchAdvice(req,await invoke(req,{signal:c.signal}),ctx.options?.hostDispatch);
        return {content:typeof result?.text==='string'&&Object.keys(result).length===1?result.text:JSON.stringify(result)};
      },
    }));
  },
};
