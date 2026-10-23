"""NON-LIVE installer integration: create-only dry-run bundles, never installed writes.

Receipts are immutable through this API (exclusive create + read-only + hash checks),
not an OS immutability/sandbox/CAS guarantee. Source conflicts stop, never overwrite.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import re

from access_policy import MODEL, absolute, agent_parts, binding_acceptance, compile_for_agent, compose_session_policy, digest, inside, matrix_document, validate, winner


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked_path(value,kind='directory',missing=False):
    value=absolute(str(value));target=Path(value);current=Path('/')
    facts=[];absent=False
    for part in target.parts[1:]:
        current=current/part
        try:info=current.lstat()
        except FileNotFoundError:
            if not missing:raise ValueError('required path missing: '+str(current))
            absent=True;break
        if stat.S_ISLNK(info.st_mode):raise ValueError('symlink in explicit binding/target: '+str(current))
        if current!=target and not stat.S_ISDIR(info.st_mode):raise ValueError('non-directory ancestor')
        facts.append({'path':str(current),'device':info.st_dev,'inode':info.st_ino,'mode':info.st_mode})
    if not absent:
        info=target.lstat()
        if (kind=='directory' and not stat.S_ISDIR(info.st_mode)) or (kind=='file' and not stat.S_ISREG(info.st_mode)):
            raise ValueError('bound path has wrong kind: '+value)
    if str(target.resolve(strict=False))!=value:raise ValueError('noncanonical realpath')
    return {'path':value,'kind':kind,'missingAllowed':missing,'missing':absent,'ancestors':facts}


def read_exact(file,expected):
    checked_path(file,'file')
    if not isinstance(expected,str) or len(expected)!=64:raise ValueError('explicit before SHA256 required')
    fd=os.open(file,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('source is not a regular file')
        data=stream.read()
    if sha(data)!=expected:raise ValueError('before-hash conflict; source left untouched')
    return data


def binding_paths(model,binding):
    validate(model,binding)
    paths=[checked_path(binding['home']),checked_path(binding['location'])]
    if binding['projectRoot']!='/':
        paths.append(checked_path(binding['projectRoot']))
        if not inside(binding['projectRoot'],binding['location']):raise ValueError('Location outside explicit native project root')
    paths += [checked_path(root) for root in binding['assignedRoots']+binding.get('recipientRoots',[])]
    paths += [checked_path(absolute(root['path'],binding['home']),missing=True) for root in model['commonReads']]
    paths += [checked_path(scope['path'],scope['kind'],missing=True)
              for scope in binding.get('ownedWrites',[])+binding.get('sharedOutputs',[])]
    comm=binding.get('communication',{})
    if comm.get('chiefPointer'):paths.append(checked_path(comm['chiefPointer'],'file',missing=True))
    if comm.get('parentDirectory'):paths.append(checked_path(comm['parentDirectory']))
    return paths


def body_bytes(raw):
    # Only supported UTF-8 LF frontmatter. No newline/voice/include rewriting.
    text=raw.decode('utf8');agent_parts(text)
    return text.split('\n---\n',1)[1].encode('utf8')


def publish(root,name,data):
    target=root/name
    with target.open('xb') as stream:
        os.chmod(target,0o600);stream.write(data);stream.flush();os.fsync(stream.fileno())
    os.chmod(target,0o400)
    return sha(data)


def check_sources(receipt):
    read_exact(receipt['modelSource'],receipt['modelBeforeSha256'])
    for role in receipt['roles']:
        read_exact(role['source'],role['beforeSha256'])
        for fact in role['paths']:
            now=checked_path(fact['path'],fact['kind'],fact['missingAllowed'])
            if now!=fact:raise ValueError('binding/root identity changed; re-review required')


def dry_run(manifest,output,model_file=MODEL):
    model_file=Path(model_file)
    checked_path(model_file,'file')
    raw_model=model_file.read_bytes();model=json.loads(raw_model)
    if set(manifest)!={'roles'} or not isinstance(manifest['roles'],list) or not manifest['roles']:
        raise ValueError('explicit role assignments required')
    matrix=matrix_document(model)
    if matrix['passed']!=matrix['total']:raise ValueError('central matrix failed; no candidate bundle')
    output=Path(absolute(str(output)))
    checked_path(output.parent)
    if '.opencode' in output.parts or output.exists() or output.is_symlink():
        raise ValueError('new non-watched candidate directory required')
    roles=[];artifacts={};visibility=[];observers=[];ids=set();sources=set()
    for entry in manifest['roles']:
        required={'binding','agentRoot','roleFile','beforeSha256'}
        if not required<=set(entry) or set(entry)-required-{'managedBaseline','observerIdentity','sessionPolicySnapshot'}:raise ValueError('unknown or missing manifest input')
        binding=entry['binding'];paths=binding_paths(model,binding)
        if binding['id'] in ids:raise ValueError('duplicate assignment')
        ids.add(binding['id'])
        root=absolute(entry['agentRoot']);source=absolute(entry['roleFile'])
        if inside(root,str(output)):raise ValueError('dry-run outputs must not enter an installed agent root')
        paths.append(checked_path(root))
        if not inside(root,source) or Path(source).parent!=Path(root) or not source.endswith('.md') or source in sources:
            raise ValueError('exact unique agent file inside bound agentRoot required')
        sources.add(source);paths.append(checked_path(source,'file'))
        before=read_exact(source,entry['beforeSha256']);text=before.decode('utf8')
        if any(rule.get('effect')=='ask' for rule in agent_parts(text)[2]):
            raise ValueError('custom ask constraints require explicit supported migration; never silently widen')
        compiled,emitted=compile_for_agent(model,binding,text,managed_baseline=entry.get('managedBaseline',[]))
        effective=compose_session_policy(compiled,entry['sessionPolicySnapshot']) if 'sessionPolicySnapshot' in entry else compiled
        if 'sessionPolicySnapshot' in entry and entry.get('observerIdentity') is not None:
            identity=entry['observerIdentity'];snapshot=entry['sessionPolicySnapshot']
            if any(identity.get(k)!=snapshot[k] for k in ('sessionID','agentID')):
                raise ValueError('session snapshot and explicit observer identity differ')
        if body_bytes(before)!=body_bytes(emitted.encode('utf8')):raise ValueError('custom prompt byte preservation failed')
        if compiled['communication']['status']!='candidate-bound':raise ValueError('explicit reporting route missing')
        transport=model['communicationTransports'][binding['communication']['transport']]
        if transport.get('action') and winner(transport['action'],'*',effective['nativeRules'])['effect']!='allow':
            raise ValueError('retained custom constraint blocks reporting; owner resolution required')
        acceptance=binding_acceptance(model,effective)
        if acceptance['passed']!=acceptance['total']:
            failed=[r['id'] for r in acceptance['rows'] if not r['pass']]
            raise ValueError('actual binding acceptance conflict; retain constraints and resolve: '+','.join(failed))
        if compiled['run']['selected'] is not None or compiled['installable']:raise ValueError('non-live unselected output required')
        stem=binding['id'];artifacts[stem+'.agent.md']=emitted.encode('utf8')
        artifacts[stem+'.acceptance.json']=(json.dumps(acceptance,indent=2)+'\n').encode()
        artifacts[stem+'.policy.json']=(json.dumps(compiled,indent=2)+'\n').encode()
        if 'sessionPolicySnapshot' in entry:
            artifacts[stem+'.effective-policy.json']=(json.dumps(effective,indent=2)+'\n').encode()
        roles.append({'bindingID':stem,'role':binding['role'],'source':source,'beforeSha256':sha(before),
            'candidate':stem+'.agent.md','candidateSha256':sha(emitted.encode('utf8')),
            'promptSha256':sha(body_bytes(before)),'paths':paths,
            'sessionPolicySnapshotDigest':digest(entry['sessionPolicySnapshot']) if 'sessionPolicySnapshot' in entry else None})
        visibility.append({'bindingID':stem,'role':binding['role'],'tools':compiled['toolVisibilityCandidate'],
             'communication':compiled['communication'],'nativeToolPresence':'unverified',
             'contextFilterIntegration':'required-not-applied'})
        identity=entry.get('observerIdentity')
        observer={'enabled':False,'candidateOnly':True,'directory':binding['location'],
            'logFile':binding['home']+'/.chief-of-staff/access/denials.jsonl','bindings':[],
            'readiness':'explicit-session-and-agent-unbound','singleWriterRequired':True}
        if identity is not None:
            if (set(identity)!={'sessionID','agentID'} or not isinstance(identity['sessionID'],str)
                or not re.fullmatch(r'ses_[A-Za-z0-9]+',identity['sessionID'])
                or not isinstance(identity['agentID'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',identity['agentID'])
                or identity['sessionID']!=binding['communication']['originSession']):
                raise ValueError('observer identity must match exact reporting origin; no inferred agent')
            roots=[{'id':'assigned-'+str(i),'path':root} for i,root in enumerate(binding['assignedRoots'])]
            roots += [{'id':r['id'],'path':absolute(r['path'],binding['home'])} for r in model['commonReads']]
            roots += [{'id':r['id'],'path':absolute(r['path'],binding['home']),'protected':True} for r in model['protectedRoots']]
            observer['bindings']=[{**identity,'compilation':effective,'pathRoots':roots,'publicPaths':[]}]
            observer['readiness']='source-bound-not-installed-or-native-verified'
        observers.append(observer)
    artifacts['matrix.json']=(json.dumps(matrix,indent=2)+'\n').encode()
    artifacts['visibility.json']=(json.dumps(visibility,indent=2)+'\n').encode()
    artifacts['observers.json']=(json.dumps(observers,indent=2)+'\n').encode()
    receipt={'schemaVersion':1,'candidateOnly':True,'installable':False,'runSelected':None,
        'fileIdentityProtection':model['fileIdentityProtection'],
        'modelSource':str(model_file),'modelBeforeSha256':sha(raw_model),'modelDigest':digest(model),'roles':roles,
        'knownSessionMigration':'not-generated-no-native-calls',
        'limits':['Dry run only; no source/installed role/session/config/options write.',
                  'Preflight/readback is not CAS, OS isolation or symlink-race prevention.',
                  'Missing explicit future outputs/common roots stay explicit, are not created or silently removed.',
                  'Tool visibility and communication are generated integration inputs, not native availability proofs.']}
    check_sources(receipt)
    output.mkdir(mode=0o700)
    receipt['artifacts']={name:publish(output,name,data) for name,data in sorted(artifacts.items())}
    check_sources(receipt)
    receipt['receiptDigest']=digest(receipt)
    publish(output,'receipt.json',(json.dumps(receipt,indent=2)+'\n').encode())
    return receipt


def verify_bundle(output):
    output=Path(absolute(str(output)));checked_path(output)
    checked_path(output/'receipt.json','file')
    receipt=json.loads((output/'receipt.json').read_bytes())
    actual=receipt.pop('receiptDigest');expected=digest(receipt);receipt['receiptDigest']=actual
    if actual!=expected:raise ValueError('receipt digest conflict')
    if not receipt.get('candidateOnly') or receipt.get('installable') or receipt.get('runSelected') is not None:
        raise ValueError('non-live receipt contract violated')
    for name,expected in receipt['artifacts'].items():
        if Path(name).name!=name:raise ValueError('artifact path escape')
        read_exact(output/name,expected)
    check_sources(receipt)
    return receipt


def activate(output):
    # There is intentionally NO live install operation hidden behind this gate.
    raise ValueError('ACTIVATION REFUSED: run.selected=null; production choice/coverage/rollout pending')
