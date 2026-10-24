"""Bounded local snapshot refresh. No agent transport, shell, root scanning or wakes.

Operator supplies the exact config path; stdin is a validated semantic invalidation only.
All files must already have explicitly approved source/destination mappings.
"""
import argparse
import copy
import fcntl
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tower_export as export
import tower_schema as schema

RASTER = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
STALE = 'Source changed; owner must write short plain headers.'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def location(value, suffixes, *, redaction=False):
    schema.obj(value, 'root path redact_private_patterns' if redaction else 'root path')
    if redaction and 'redact_private_patterns' in value and type(value['redact_private_patterns']) is not bool:
        raise ValueError('redaction opt-in must be boolean')
    export.root(value.get('root')); export.relative(value.get('path'), suffixes)
    return value


def read_json(where):
    return json.loads(export.read_exact(where['root'], where['path'], {'.json'}))


def plain(value):
    return (type(value) is str and 0 < len(value) <= 100 and value == value.strip()
            and '\n' not in value and not re.search(
                r'[0-9a-f]{7,}|(?:ses_|msg_|ev\.)\w+|[/\\]|\b[A-Z]{3,}\d+', value, re.I))


def principal_header(raw):
    fields = {}
    for line in raw.decode('utf-8').splitlines()[:30]:
        if line.startswith('## '): break
        key, sep, value = line.partition(':')
        key, value = key.lower(), value.strip()
        if sep and key in ('status', 'usable now', 'left', 'waiting on', 'needs you', 'handed to'):
            if key in fields: raise ValueError('ambiguous principal header')
            fields[key] = value
    if any(not plain(fields.get(k)) for k in ('status', 'usable now', 'left', 'waiting on')):
        return None
    if len(fields['status']) > 80: return None # Preserve the existing manifest status bound.
    if fields.get('needs you') not in ('true', 'false'): return None
    if 'handed to' in fields and not plain(fields['handed to']): return None
    fields['needs_you'] = fields.pop('needs you') == 'true'
    return fields


def configuration(value):
    schema.depth(value); schema.obj(value, 'version export_config manifest projects docket')
    if type(value.get('version')) is not int or value['version'] != 1: raise ValueError('config version')
    location(value.get('export_config'), {'.json'})
    if 'manifest' in value: location(value['manifest'], {'.json'})
    if 'docket' in value:
        schema.obj(value['docket'],'executable')
        p = Path(schema.text(value['docket'].get('executable'),4096))
        if not p.is_absolute() or p.resolve() != p: raise ValueError('canonical Docket executable required')
    ids, origins, targets = set(), set(), set()
    for row in schema.seq(value.get('projects'), 100):
        schema.obj(row, 'project_id session directory header copies migration')
        pid = schema.ident(row.get('project_id')); session = schema.ident(row.get('session'))
        if not session.startswith('ses_'): raise ValueError('session required')
        export.root(row.get('directory'))
        origin = (session, row['directory'])
        if pid in ids or origin in origins: raise ValueError('duplicate binding')
        ids.add(pid); origins.add(origin); location(row.get('header'), {'.md'}, redaction=True)
        for entry in schema.seq(row.get('copies'), 100):
            schema.obj(entry, 'source target redact_private_patterns')
            if 'redact_private_patterns' in entry and (type(entry['redact_private_patterns']) is not bool or Path(entry.get('source',{}).get('path','')).suffix.lower() != '.md'):
                raise ValueError('text-only boolean redaction opt-in required')
            source = location(entry.get('source'), {'.md'} | RASTER)
            target = location(entry.get('target'), {'.md'} | RASTER)
            pair = (target['root'], target['path'])
            if pair in targets or source == target or Path(source['path']).suffix != Path(target['path']).suffix:
                raise ValueError('unsafe/duplicate copy target')
            targets.add(pair)
        if 'migration' in row:
            m = schema.obj(row['migration'], 'sha256 summary status')
            if not re.fullmatch('[0-9a-f]{64}', schema.text(m.get('sha256'),64)): raise ValueError('digest required')
            if not plain(m.get('status')) or len(m['status']) > 80: raise ValueError('plain migration status required')
            s = m.get('summary')
            probe = dict(version=1, project_id=pid, outcome_id='probe', generated_at=datetime.now(timezone.utc).isoformat(), summary=s)
            schema.projection(probe, pid, 'probe')
            if any(not plain(s.get(k)) for k in ('usable now','left','waiting on')): raise ValueError('plain migration required')
    export.sanitize(value)
    return value


def marker(value):
    schema.obj(value, 'id version lead_session directory milestone_at milestone_ref observed_at roster_state provenance')
    if not re.fullmatch('mil_[0-9a-f]{64}', schema.ident(value.get('id'))): raise ValueError('marker id')
    if type(value.get('version')) is not int or value['version'] != 1: raise ValueError('marker version')
    if not schema.ident(value.get('lead_session')).startswith('ses_'): raise ValueError('marker session')
    export.root(value.get('directory'))
    if schema.stamp(value.get('milestone_at')) > schema.stamp(value.get('observed_at')): raise ValueError('marker time order')
    schema.text(value.get('milestone_ref'),1000)
    if value.get('roster_state') not in ('active','hold','done'): raise ValueError('marker roster state')
    if value.get('provenance') != 'recorded_marker_observation': raise ValueError('marker provenance')
    export.sanitize(value)
    return value


def invalidation(value):
    schema.obj(value, 'version kind marker')
    if type(value.get('version')) is not int or value['version'] != 1: raise ValueError('invalidation version')
    if value.get('kind') not in ('periodic','milestone','startup'): raise ValueError('invalidation kind')
    if value['kind'] == 'milestone': marker(value.get('marker'))
    elif 'marker' in value: raise ValueError('unexpected marker')
    return value


def checked_text(raw, enabled=False):
    text = raw.decode('utf-8'); count = 0
    if enabled:
        text, count = export.SECRET.subn('[redacted private-pattern text]', text)
    export.sanitize(text)
    return text.encode('utf-8'), count


def checked_copy(entry):
    source, target = entry['source'], entry['target']
    suffix = Path(source['path']).suffix.lower()
    raw = export.read_exact(source['root'], source['path'], {'.md'} | RASTER)
    count = 0
    if suffix == '.md': raw, count = checked_text(raw, entry.get('redact_private_patterns', False))
    else:
        valid = (raw.startswith(b'\x89PNG\r\n\x1a\n') if suffix == '.png' else
                 raw.startswith(b'\xff\xd8\xff') if suffix in ('.jpg','.jpeg') else
                 raw.startswith((b'GIF87a', b'GIF89a')) if suffix == '.gif' else
                 raw[:4] == b'RIFF' and raw[8:12] == b'WEBP')
        if not valid: raise ValueError('invalid raster')
        export.sanitize(raw.decode('latin1'))
    return target, raw, {suffix}, count


def refresh(config, notice, *, acceptance=export.acceptance_read, markers=()):
    """Injected already-validated marker read repairs lost best-effort invalidations."""
    config = configuration(config); notice = invalidation(notice)
    rows = export.configuration(read_json(config['export_config']))['projects']
    indexed = {r['project']['id']: r for r in rows}
    observations = [marker(m) for m in markers]
    if notice['kind'] == 'milestone': observations.append(notice['marker'])
    ready, documents, statuses, stale, redactions = [], [], {}, [], 0
    for spec in config['projects']:
        row = indexed[spec['project_id']]; p = row['project']
        # Cache is exact identity-bound projection, not background Knowledge impersonation.
        out = copy.deepcopy(read_json(p['export']))
        schema.projection(out, p['id'], p['outcome_id'])
        approved = {(f.get('root',p['root']), f['path']) for f in p.get('files',[])}
        approved |= {(p['root'], f['path']) for f in p.get('images',[])}
        for entry in spec['copies']:
            if (entry['target']['root'], entry['target']['path']) not in approved:
                raise ValueError('copy target not in project allowlist')
            document = checked_copy(entry)
            documents.append(document); redactions += document[3]
        raw = export.read_exact(spec['header']['root'], spec['header']['path'])
        sha = digest(raw) # Migration evidence always binds ORIGINAL bytes, never redacted copies.
        cleaned, count = checked_text(raw, spec['header'].get('redact_private_patterns', False))
        redactions += count
        current = principal_header(cleaned)
        if current and any('[redacted private-pattern text]' in v for v in current.values() if type(v) is str):
            current = None # Redaction is not a principal-facing capability translation.
        previous = out.get('summary', {})
        if current:
            statuses[p['id']] = current.pop('status')
            if previous.get('reference') != 'sha256:'+sha:
                out['summary'] = dict(current, observed_at=datetime.now(timezone.utc).isoformat(),
                                      provenance='Approved local principal header', reference='sha256:'+sha)
        elif spec.get('migration', {}).get('sha256') == sha:
            out['summary'] = copy.deepcopy(spec['migration']['summary'])
            statuses[p['id']] = spec['migration']['status']
        else:
            stale.append(p['id'])
            if previous:
                previous['provenance'] = previous['provenance'].split(' · '+STALE)[0] + ' · ' + STALE
        if 'acceptance_request_id' in row:
            out['acceptance'] = acceptance(row['acceptance_request_id'])
        activity = out.setdefault('activity', [])
        for m in observations:
            if (m['lead_session'],m['directory']) != (spec['session'],spec['directory']): continue
            # Observation may be historical: today's capability is not source-time evidence.
            eid = m['id']
            if any(e['id'] == eid for e in activity): continue
            activity.append(dict(id=eid, project_id=p['id'],outcome_id=p['outcome_id'],kind='landing',
                                 at=m['milestone_at'], label='New work was delivered.',
                                 reference=(m['milestone_ref'] if len(m['milestone_ref'])<=500 else
                                            'Docket marker '+eid+'; reference sha256:'+digest(m['milestone_ref'].encode())),
                                 provenance=m['provenance']))
        out['activity'] = sorted(activity,key=lambda e:schema.stamp(e['at']))[-500:]
        out['generated_at'] = datetime.now(timezone.utc).isoformat()
        schema.projection(out,p['id'],p['outcome_id']); export.sanitize(out)
        ready.append((p['export'],out))
    manifest = None
    if 'manifest' in config:
        manifest = read_json(config['manifest']); schema.obj(manifest,'version projects')
        if type(manifest.get('version')) is not int or manifest['version'] != 1: raise ValueError('manifest version')
        for p in schema.seq(manifest.get('projects'),100):
            if p.get('id') in statuses:
                if p.get('outcome_id') != indexed[p['id']]['project']['outcome_id']: raise ValueError('manifest outcome')
                p['status'] = statuses[p['id']]
        export.sanitize(manifest)
    # Every read/validation/privacy check completes before any replacement. Each file atomic;
    # not a cross-file transaction. On I/O failure retry safely with old valid projections retained.
    for target, raw, suffixes, _ in documents: export.atomic_bytes(target,raw,suffixes)
    for target,out in ready: export.atomic_write(target,out)
    if manifest is not None: export.atomic_write(config['manifest'],manifest)
    return {'version':1,'refreshed':len(ready),'stale_sources':stale,'redactions':redactions}


def refresh_knowledge(config, reader=export.knowledge_read):
    """Explicit genuine agent-context entry; no supplied session or credentials accepted."""
    config = configuration(config)
    indexed = {r['project']['id']:r for r in export.configuration(read_json(config['export_config']))['projects']}
    ready = []
    for spec in config['projects']:
        row = copy.deepcopy(indexed[spec['project_id']]); p = row['project']
        out = read_json(p['export']); schema.projection(out,p['id'],p['outcome_id'])
        for f in p.get('files',[]):
            target = {'root':f.get('root',p['root']),'path':f['path']}
            match = next((c['source'] for c in spec['copies'] if c['target'] == target),None)
            if match: f.update(match)
        knowledge = export.project_knowledge(row,lambda _:reader(spec['directory']))
        if knowledge['state'] != 'available': raise ValueError('Knowledge read failed; old cache retained')
        out['knowledge'] = knowledge; out['generated_at'] = datetime.now(timezone.utc).isoformat()
        schema.projection(out,p['id'],p['outcome_id']); export.sanitize(out)
        ready.append((p['export'],out))
    for target,out in ready: export.atomic_write(target,out)
    return {'version':1,'refreshed':len(ready),'stale_sources':[]}


def main():
    parser = argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('config',help='exact operator-owned refresh JSON config')
    parser.add_argument('--knowledge',action='store_true',help='refresh notes/todos only in genuine inherited agent context; no background fallback')
    args = parser.parse_args(); path = Path(args.config)
    # Serializes handler/startup overlap. Operator-controlled config ancestry is trusted.
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        config = configuration(read_json(location({'root':str(path.parent),'path':path.name},{'.json'})))
        if args.knowledge:
            print(json.dumps(refresh_knowledge(config))); return
        raw = sys.stdin.buffer.read(16385)
        if len(raw) > 16384: raise ValueError('invalidation bound')
        notice = invalidation(json.loads(raw))
        observations = []
        if 'docket' in config:
            from tower_refresh_docket import Docket
            client = Docket(config['docket']['executable'])
            client.reconcile()
            observations = client.markers()
        print(json.dumps(refresh(config,notice,markers=observations)))
    finally: os.close(fd)


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        error = 'lease_expired' if str(exc) == 'Snapshot lease expired; owner must explicitly renew' else 'refresh_refused'
        print(json.dumps({'version':1,'error':error}))
        raise SystemExit(1)
