// Source descriptors only; not live agent/config registration or a public owner schema.
export function permissions(role) {
  const names={lead:['desk_report'],desk:['desk_inbox','desk_project_sync','desk_propose'],chief:['desk_decision']}[role];
  if (!names) throw Error('unknown optional native role');
  return [{action:'*',resource:'*',effect:'deny'},...names.map(action=>({action,resource:'*',effect:'allow'}))];
}
