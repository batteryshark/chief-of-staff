// Pure inert config builder. No filesystem writes, native calls or invented IDs.
import path from 'node:path';
import {permissions} from './catalog.mjs';

export const agents={
  'proof-lead-a':{role:'lead',location:'lead-a'},
  'proof-lead-b':{role:'lead',location:'lead-b'},
  'proof-desk':{role:'desk',location:'home'},
  'proof-chief':{role:'chief',location:'home'},
};
export function pendingConfig(root,python) {
  if (!path.isAbsolute(root) || path.normalize(root)!==root || !path.isAbsolute(python)) throw Error('absolute canonical fixture paths required');
  const systems={lead:'Owned throwaway lead. Use only desk_report for the supplied fixture report. No delegation or goals.',
    desk:'Owned throwaway desk. Use desk_inbox on the exact supplied native inputId, then desk_project_sync if pending. Never infer approval.',
    chief:'Owned throwaway chief, not the principal. Only desk_decision; no principal approval, shell or delegation.'};
  return {plugins:[{package:path.join(root,'fixture-plugin'),options:{enabled:false,root,python}}],
    agents:Object.fromEntries(Object.entries(agents).map(([name,{role}])=>[name,{
      mode:'primary',steps:4,system:systems[role],permissions:permissions(role),
    }]))};
}
