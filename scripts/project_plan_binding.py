"""Source-only plan binding from trusted adapter snapshots, never model arguments.

No live resolver is provided. The caller must obtain session, project and Knowledge
snapshots independently from their authoritative owners. Equality is not provenance.
Filesystem checks reject observed aliases, not concurrent swaps or native case aliases.
"""
import os
from pathlib import Path
import stat


def private_identity(path):
    """Read metadata only; reject symlink ancestors, foreign ownership and hardlinks."""
    p = Path(path)
    if not p.is_absolute() or str(p) != path or '..' in p.parts:
        raise ValueError('literal absolute identity required')
    for ancestor in [*reversed(p.parents), p]:
        info = ancestor.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ValueError('symlink identity refused')
    info = p.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
        raise ValueError('owned single-link plan required')
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns]


def bind_project_plans(binding, session, project, knowledge):
    """Candidate receipt, requiring a separate owner-resolved project root record.

    `project`: sessionID, directory, projectId, plansRoot from the trusted resolver.
    This interface is NOT implemented by accepting a model's projectId or directory.
    """
    from access_policy import absolute, digest
    if (binding['role'] != 'lead' or session.get('agent') != 'lead'
            or session.get('id') != binding.get('communication', {}).get('originSession')
            or session.get('location', {}).get('directory') != binding['location']
            or session.get('time', {}).get('archived')
            or set(project) != {'sessionID', 'directory', 'projectId', 'plansRoot'}
            or project['sessionID'] != session['id'] or project['directory'] != binding['location']
            or project['projectId'] != knowledge.get('projectId')):
        raise ValueError('independent native session/project/Knowledge binding required')
    root = absolute(project['plansRoot'])
    pid = project['projectId']
    if (not isinstance(pid, str) or not pid or any(c in pid for c in '/\\.*?\x00\n\r')
            or root != binding['home']+'/.config/openchamber/projects/'+pid+'/plans'):
        raise ValueError('owner-resolved personal plan root required')
    plans = knowledge.get('plans')
    if not isinstance(plans, list) or not plans:
        raise ValueError('listed existing plans required')
    files = []
    ids = set()
    for plan in plans:
        target = absolute(plan['path'])
        if (plan.get('source') != 'personal' or str(Path(target).parent) != root
                or not target.endswith('.md') or not isinstance(plan.get('id'), str)
                or not plan['id'] or plan['id'] in ids or target in files):
            raise ValueError('unique listed personal plan required; no shared/foreign grant')
        private_identity(target)
        ids.add(plan['id']); files.append(target)
    return {**binding, 'projectPlans': {'sessionID':session['id'], 'directory':binding['location'],
        'projectId':pid, 'root':root, 'files':files,
        'evidenceDigest':digest({'session':session,'project':project,'knowledge':knowledge}),
        'status':'source-only-unverified-native-identity'}}
