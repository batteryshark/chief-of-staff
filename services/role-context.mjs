// managed by chief-of-staff/install.sh
// Request-local diet: never grant permissions or replace agent/provider prompts.
const common = ['read', 'glob', 'grep', 'patch', 'edit', 'write', 'skill', 'execute',
  'question', 'webfetch', 'websearch', 'subagent', 'runway', 'openchamber',
  'openchamber_knowledge', 'a2a_*', 'canvas_*', 'openchamber_render',
  'opencode_list_mcp_resources', 'opencode_read_mcp_resource',
  'opencode_session_move', 'opencode_session_rename', 'opencode_worktree_list',
  'chief_post', 'chief_wait', 'chief_wait_time', 'chief_resume_time',
  'docket_*'];
export const tools = {
  chief: [...common, 'shell', 'heartbeat_close', 'heartbeat_status', 'heartbeat_reconcile',
    'openchamber_schedule', 'openchamber_web', 'nod_*', 'fleet_*', 'chief_call', 'chief_urgent_call'],
  lead: [...common, 'shell', 'openchamber_web', 'fleet_*'],
  writer: [...common, 'shell', 'openchamber_web', 'galley_*', 'gpt_image*', 'image_*'],
  dispatcher: ['heartbeat_resolve'],
};
export const skills = {
  chief: ['checkpoint', 'reset-*', 'upstream-courtesy', 'shape', 'deep-research'],
  lead: ['checkpoint', 'reset-*', 'upstream-courtesy', 'shape', 'deep-research',
    'opencode', 'delivery-outlook', 'comparative-review', 'report', 'pdf', 'docs',
    'docx', 'xlsx', 'pptx', 'google-workspace', 'built-in-browser', 'chrome-browser',
    'computer-use', 'gpt-image', 'skill-creator'],
  writer: ['checkpoint', 'deep-research', 'upstream-courtesy', 'gpt-image',
    'docs', 'docx', 'pdf', 'google-workspace', 'built-in-browser', 'chrome-browser'],
  dispatcher: [],
};
export function matches(name, patterns) {
  return patterns.some(pattern => new RegExp('^' + pattern.split('*')
    .map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$').test(name));
}
export function roleFor(agent) {
  return ({'chief-of-staff': 'chief', lead: 'lead', writer: 'writer',
    'heartbeat-pilot-dispatcher': 'dispatcher'})[agent];
}
export function filterTools(event, roleTools = tools) {
  const role = roleFor(event.agent);
  if (!role) return; // Build/general/explore retain the native coding base and tools.
  const allowed = roleTools[role];
  if (!Array.isArray(allowed)) return;
  for (const name of Object.keys(event.tools)) {
    if (!matches(name, allowed)) delete event.tools[name];
  }
}
export async function setup(ctx) {
  // Permissions are compiled at install time from fully loaded inventories.
  // Never capture early startup registries or rewrite provider/harness catalogs.
  // Writer tool dependencies require a reviewed exact inventory; do not guess
  // aliases and silently remove a live Galley tool while that inventory is absent.
  const roleTools = {...tools, writer: undefined, ...ctx.options?.roleTools};
  const hook = await ctx.session.hook('context', event => filterTools(event, roleTools));
  return async () => { await hook.dispose(); };
}
export default {id: 'chief-role-context', setup};
