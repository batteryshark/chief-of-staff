// managed by chief-of-staff/install.sh; one shared identity-bound registration.
import {readFile} from 'node:fs/promises';
import {createMilestonePlugin} from './milestone.mjs';
export default {id:'chief-own-milestone',async setup(ctx){
  const binding=JSON.parse(await readFile(new URL('./binding.json',import.meta.url),'utf8'));
  if(!binding.callers.some(c=>c.directory===ctx.location.directory))return;
  return createMilestonePlugin(binding).setup(ctx);
}};
