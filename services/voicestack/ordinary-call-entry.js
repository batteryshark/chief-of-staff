// managed by chief-of-staff; scoped ordinary CLI, no managed grants.
import {writeFile} from 'node:fs/promises';
import {atLeast} from __VERSION_MODULE__;
import {createOrdinaryCallPlugin} from __CALL_MODULE__;
const binding=__BINDING__;
export default {id:'chief-ordinary-call',async setup(ctx){
  if(ctx.location.directory!==binding.directory||!atLeast(ctx.app.version,'2.0.32'))return;
  const stop=await createOrdinaryCallPlugin(binding).setup(ctx);
  try {
    const tools=await ctx.tool.list();const tool=tools.find(t=>t.id==='chief_urgent_call');
    if(!tool)throw Error('ordinary call tool not registered');
    await writeFile(__STATUS_FILE__,JSON.stringify({ready:true,at:Date.now(),pid:process.pid,version:ctx.app.version,
      location:ctx.location.directory,tool:tool.id,input:tool.input,binding,managedAvailable:false},null,2)+'\n');
    return stop;
  } catch(error){await stop?.();throw error;}
}};
