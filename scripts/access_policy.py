#!/usr/bin/env python3
"""NON-LIVE central policy compiler/matrix. No host calls or installed file writes.

POSIX lexical native resource contract only. Not an OS sandbox or symlink check.
Run profiles are classifications, never selected/activated by this candidate.
"""
import argparse
import hashlib
import json
import posixpath as path
from pathlib import Path
import re

MODEL = Path(__file__).resolve().parents[1]/'access/model.json'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def absolute(value, home=None):
    if not isinstance(value,str):raise ValueError('path must be a literal string')
    if home and value.startswith('$HOME/'):
        value = home + value[5:]
    if (not isinstance(value,str) or not value.startswith('/') or value=='/'
            or path.normpath(value)!=value or any(c in value for c in '*?\\\x00\n\r')):
        raise ValueError('literal canonical POSIX root/file required; no patterns or inferred roots')
    return value


def inside(root, target):
    return target==root or target.startswith(root+'/')


def wildcard(value, pattern):
    # Native Wildcard.match: whole value, * crosses slash, [] has no special meaning.
    def escaped(p):
        return ''.join('.*' if c=='*' else '.' if c=='?' else re.escape(c) for c in p)
    pattern=pattern.replace('\\','/');value=value.replace('\\','/')
    regex=escaped(pattern[:-2])+'( .*)?' if pattern.endswith(' *') else escaped(pattern)
    return re.fullmatch(regex,value,re.S) is not None


def winner(action, resource, rules):
    return next((r for r in reversed(rules) if wildcard(action,r['action']) and wildcard(resource,r['resource'])),
                {'action':action,'resource':'*','effect':'ask'})


def native_rule(rule, home):
    rule=dict(rule)
    if rule['action'] in ('read','edit','external_directory'):
        for prefix in ('$HOME/','~/'):
            if rule['resource'].startswith(prefix):
                rule['resource']=home+'/'+rule['resource'][len(prefix):];break
    return rule


def resources(requested, binding, kind='file'):
    value=binding['home']+requested[1:] if requested.startswith('~/') else requested
    target=path.normpath(value if value.startswith('/') else path.join(binding['location'],value))
    internal=inside(binding['location'],target) or (binding['projectRoot']!='/' and inside(binding['projectRoot'],target))
    if internal:
        return {'absolute':target,'resource':path.relpath(target,binding['location']),'external':None}
    directory=target if kind=='directory' else path.dirname(target)
    return {'absolute':target,'resource':target,'external':directory+'/*'}


def validate(model, binding):
    allowed={'id','role','home','location','projectRoot','assignedRoots','ownedWrites','sharedOutputs','recipientRoots','runProfile','communication','ownMilestone','launchContract','launchObservation','projectPlans','planCheckbox'}
    if set(binding)-allowed or not {'id','role','home','location','projectRoot','assignedRoots'} <= set(binding):
        raise ValueError('explicit binding fields required; unknown assignment fields refused')
    if binding['role'] not in model['roles']:
        raise ValueError('unbound/unknown specialist role')
    for key in ('home','location'):
        absolute(binding[key])
    checkbox=binding.get('planCheckbox')
    if checkbox is not None:
        if (binding['role'] not in model['nativeCapabilities']['planCheckbox']['roles'] or not isinstance(checkbox,dict)
                or set(checkbox)!={'sessionID','agentID','directory','planIDs'} or checkbox['agentID']!='lead'
                or not isinstance(checkbox['sessionID'],str) or not re.fullmatch(r'ses_[A-Za-z0-9]+',checkbox['sessionID'])
                or checkbox['sessionID']!=binding.get('communication',{}).get('originSession')
                or checkbox['directory']!=binding['location'] or not isinstance(checkbox['planIDs'],list) or not checkbox['planIDs']
                or any(not isinstance(p,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',p) for p in checkbox['planIDs'])
                or len(set(checkbox['planIDs']))!=len(checkbox['planIDs'])):
            raise ValueError('explicit trusted own checkbox binding required')
    plans=binding.get('projectPlans')
    if plans is not None:
        if (binding['role'] not in model['projectPlans']['roles'] or not isinstance(plans,dict)
                or set(plans)!={'sessionID','directory','projectId','root','files','evidenceDigest','status'}
                or plans['status']!=model['projectPlans']['status']
                or plans['directory']!=binding['location']
                or plans['sessionID']!=binding.get('communication',{}).get('originSession')
                or not isinstance(plans['projectId'],str) or not re.fullmatch(r'[A-Za-z0-9_-]+',plans['projectId'])
                or plans['root']!=binding['home']+'/.config/openchamber/projects/'+plans['projectId']+'/plans'
                or not isinstance(plans['evidenceDigest'],str) or not re.fullmatch(r'[a-f0-9]{64}',plans['evidenceDigest'])
                or not isinstance(plans['files'],list) or not plans['files']):
            raise ValueError('explicit owner-resolved project plan snapshot required')
        absolute(plans['root'])
        if len(set(plans['files']))!=len(plans['files']):raise ValueError('duplicate plans')
        for file in plans['files']:
            absolute(file)
            if path.dirname(file)!=plans['root'] or not file.endswith('.md'):raise ValueError('foreign or unlisted plan root')
    milestone=binding.get('ownMilestone')
    if milestone is not None:
        if (binding['role'] not in model['nativeCapabilities']['ownMilestone']['roles']
                or not isinstance(milestone,dict) or set(milestone)!={'sessionID','agentID','directory'}
                or not re.fullmatch(r'ses_[A-Za-z0-9]+',milestone.get('sessionID',''))
                or not re.fullmatch(r'[A-Za-z0-9_-]+',milestone.get('agentID',''))
                or milestone['directory']!=binding['location']):
            raise ValueError('explicit own milestone native identity required')
    launch_acceptance(model,binding.get('launchContract'),binding.get('launchObservation'))
    if binding['projectRoot']!='/':absolute(binding['projectRoot'])
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',binding['id']):raise ValueError('safe binding id required')
    for root in [*binding['assignedRoots'],*binding.get('recipientRoots',[])]:
        absolute(root)
        if inside(root,binding['home']):raise ValueError('whole home/ancestor is not a project assignment')
    if not binding['assignedRoots']:raise ValueError('assignment cannot be inferred from cwd')
    if binding.get('runProfile') is not None and binding['runProfile'] not in model['runProfiles']:
        raise ValueError('unknown run classification')
    protected=[absolute(r['path'],binding['home']) for r in model['protectedRoots']]
    if any(inside(p,binding['location']) for p in protected):raise ValueError('Location is inside protected data')
    writes=[*binding.get('ownedWrites',[]),*binding.get('sharedOutputs',[])]
    if writes and not model['roles'][binding['role']]['writes']:raise ValueError('this role has no write capability')
    for scope in writes:
        if set(scope)!={'path','kind'} or scope['kind'] not in ('file','directory'):raise ValueError('explicit typed write scope required')
        absolute(scope['path'])
        if scope['path']==binding['home'] or any(inside(p,scope['path']) or inside(scope['path'],p) for p in protected):
            raise ValueError('write scope intersects protected data or the whole home')
    for scope in binding.get('ownedWrites',[]):
        if not any(inside(r,scope['path']) for r in binding['assignedRoots']):raise ValueError('owned write outside assignment')
    output_roots=[absolute(p,binding['home']) for p in model['sharedOutputRoots']]+binding.get('recipientRoots',[])
    for scope in binding.get('sharedOutputs',[]):
        if not any(inside(r,scope['path']) for r in output_roots):raise ValueError('shared output is not explicitly rooted')
    comm=binding.get('communication')
    if comm is not None:
        if (set(comm)-{'transport','originSession','originDirectory','chiefPointer','parentSession','parentDirectory','inboxOutput'}
                or not {'transport','originSession','originDirectory'}<=set(comm)):
            raise ValueError('explicit bounded communication fields required')
        if comm['transport'] not in model['roles'][binding['role']]['communication']:
            raise ValueError('role cannot route to this owner; workers use their parent')
        if not re.fullmatch(r'ses_[A-Za-z0-9]+',comm['originSession']) or comm['originDirectory']!=binding['location']:
            raise ValueError('original session/directory binding differs')
        transport=model['communicationTransports'][comm['transport']]
        if transport['target']=='current-chief' and comm.get('chiefPointer')!=absolute(model['currentChiefPointer'],binding['home']):
            raise ValueError('current chief requires the sole fresh pointer, not a cached session')
        if transport['target']=='parent':
            if not re.fullmatch(r'ses_[A-Za-z0-9]+',comm.get('parentSession','')) or comm['parentSession']==comm['originSession']:
                raise ValueError('exact original parent binding required')
            absolute(comm.get('parentDirectory'))
        if comm['transport']=='chief-inbox':
            output={'path':comm.get('inboxOutput'),'kind':'file'}
            if output not in binding.get('sharedOutputs',[]) or not inside(path.dirname(comm['chiefPointer'])+'/inbox',output['path']):
                raise ValueError('chief inbox requires an explicit OWN output file, not the whole inbox')


def communication(model,binding):
    comm=binding.get('communication')
    if comm is None:return {'status':'unbound-no-reporting-route','toolAvailability':'unverified','nativeProof':False}
    transport=model['communicationTransports'][comm['transport']]
    result={'status':'candidate-bound','binding':comm,'target':transport['target'],'requiredAdmission':transport['requires'],
            'toolAvailability':'unverified','nativeProof':False}
    if comm['transport']=='chief-post':
        result['requiredBusBinding']={'originSessions':[comm['originSession']],
            'originDirectories':{comm['originSession']:comm['originDirectory']},
            'chiefPointerFile':comm['chiefPointer'],'goalEnrollment':'preserve-existing-do-not-add',
            'state':'candidate-not-enrolled'}
    return result


def milestone_admission(model,binding,caller,enrollment):
    """Offline contract comparison only; runtime supplies native identity/row evidence."""
    expected=binding.get('ownMilestone')
    return ('allow' if binding['role'] in model['nativeCapabilities']['ownMilestone']['roles']
            and expected is not None and caller==expected
            and enrollment=={'sessionID':expected['sessionID'],'directory':expected['directory']} else 'deny')


def checkbox_admission(model,binding,caller,plan_id):
    expected=binding.get('planCheckbox')
    return ('allow' if expected and binding['role'] in model['nativeCapabilities']['planCheckbox']['roles']
            and caller=={k:expected[k] for k in ('sessionID','agentID','directory')}
            and plan_id in expected['planIDs'] else 'deny')


def launch_acceptance(model,contract=None,observation=None):
    """Candidate interface, never promote self-asserted fields to launcher proof."""
    if contract is None:
        if observation is not None:raise ValueError('launch observation needs an explicit declared contract')
        return {'status':'not-required','nativeProof':False}
    if (not isinstance(contract,dict) or set(contract)!=set(model['specialistLaunch']['requiredFields'])
            or not isinstance(contract['model'],dict) or set(contract['model'])!={'providerID','modelID','variant'}
            or not all(isinstance(v,str) and v for v in contract['model'].values())
            or not all(isinstance(contract[k],str) and contract[k] for k in ('launcherID','agentID'))
            or not isinstance(contract['sessionID'],str) or not re.fullmatch(r'ses_[A-Za-z0-9]+',contract['sessionID'])
            or not all(isinstance(contract[k],str) and re.fullmatch(r'[a-f0-9]{64}',contract[k]) for k in ('sessionPolicyDigest','bindingDigest'))):
        raise ValueError('exact declared launcher agent/model/Location/session-policy/binding contract required')
    absolute(contract['directory'])
    reason='launcher-provenance-unverified'
    if observation is not None:
        if not isinstance(observation,dict):raise ValueError('launch observation must be an object')
        if observation.get('method')=='generic-session':reason='outside-declared-launcher'
        elif any(observation.get(k)!=v for k,v in contract.items()):reason='launch-identity-contract-mismatch'
    return {'status':'not-ready','reason':reason,'nativeProof':False,'receiptAdapter':None}


def compile_policy(model, binding, custom_denies=()):
    validate(model,binding)
    rules=[];manifest=[]
    def add(id,action,resource,effect,reason):
        rule={'action':action,'resource':resource,'effect':effect}
        rules.append(rule);manifest.append({'id':id,'reason':reason,**rule})
    add('base.default-deny','*','*','deny','default-deny')
    reads=[{'id':r['id'],'path':absolute(r['path'],binding['home']),'kind':'directory','reason':'common-read'} for r in model['commonReads']]
    reads += [{'id':'assigned-'+str(i), 'path':r,'kind':'directory','reason':'assigned-read'} for i,r in enumerate(binding['assignedRoots'])]
    if binding.get('communication',{}).get('transport')=='chief-inbox':
        reads.append({'id':'communication-pointer','path':binding['communication']['chiefPointer'],
                      'kind':'file','reason':'communication-bound'})
    writes=[{'id':'owned-'+str(i),'reason':'owned-write',**s} for i,s in enumerate(binding.get('ownedWrites',[]))]
    writes += [{'id':'output-'+str(i),'reason':'shared-output',**s} for i,s in enumerate(binding.get('sharedOutputs',[]))]
    plan_scopes=[{'id':'project-plan-'+str(i),'reason':'own-project-plan','path':p,'kind':'file'}
                 for i,p in enumerate(binding.get('projectPlans',{}).get('files',[]))]
    reads += plan_scopes;writes += plan_scopes
    for scope in reads+writes:
        directory=scope['path'] if scope['kind']=='directory' else path.dirname(scope['path'])
        add(scope['id']+'.external','external_directory',directory+'/*','allow',scope['reason'])
    def scopes(action, items):
        # An ancestor scope needs '*' for local descendants. Clamp traversal and
        # absolute resources BEFORE adding other explicit scope grants. Otherwise
        # '*' accidentally authorizes ../siblings and externally gated read-only roots.
        ancestors=[s for s in items if s['kind']=='directory' and inside(s['path'],binding['location'])]
        if ancestors:
            outer=min(ancestors,key=lambda s:len(s['path']))
            depth=0 if outer['path']==binding['location'] else len(path.relpath(binding['location'],outer['path']).split('/'))
            add(action+'.internal',''+action,'*','allow',outer['reason'])
            add(action+'.parent-clamp',action,'../'*(depth+1)+'*','deny','normalization-clamp')
        add(action+'.absolute-clamp',action,'/*','deny','normalization-clamp')
        for s in items:
            target=resources(s['path'],binding,kind=s['kind'])
            values=[s['path']]
            if s['kind']=='directory':values.append(s['path']+'/*')
            if target['external'] is None and s not in ancestors:
                values.append(target['resource'])
                if s['kind']=='directory':values.append(target['resource']+'/*')
            for i,value in enumerate(dict.fromkeys(values)):
                add(s['id']+'.'+action+'.'+str(i),action,value,'allow',s['reason'])
    scopes('read',reads);scopes('edit',writes)
    role_actions=model['roles'][binding['role']]['nativeActions']
    for action in role_actions:
        add('role.'+action,action,'*','allow','role-capability')
    reporting=communication(model,binding)
    comm_action=model['communicationTransports'][binding['communication']['transport']].get('action') if binding.get('communication') else None
    if comm_action and comm_action not in role_actions:
        add('communication.'+comm_action,comm_action,'*','allow','communication-bound')
    milestone=model['nativeCapabilities']['ownMilestone'] if binding.get('ownMilestone') else None
    if milestone:add('capability.own-milestone',milestone['action'],milestone['resource'],'allow','own-milestone-bound')
    checkbox=model['nativeCapabilities']['planCheckbox'] if binding.get('planCheckbox') else None
    if checkbox:add('capability.plan-checkbox',checkbox['action'],checkbox['resource'],'allow','own-plan-checkbox')
    # Credential owners operate through their own trusted operation boundary;
    # there is deliberately NO native file-read exception for a credential tool.
    for item in model['protectedRoots']:
        root=absolute(item['path'],binding['home']);target=resources(root,binding,'directory')
        values=[root,root+'/*']
        if target['external'] is None:values += [target['resource'],target['resource']+'/*']
        for action in ('read','edit','external_directory'):
            for i,value in enumerate(dict.fromkeys(values)):
                add('secret.'+item['id']+'.'+action+'.'+str(i),action,value,'deny','secret-owner-only')
    for item in model['protectedFiles']:
        values=[item['pattern']] if 'pattern' in item else [absolute(item['path'],binding['home'])]
        if 'path' in item:
            target=resources(values[0],binding)
            if target['external'] is None:values.append(target['resource'])
        for action in ('read','edit'):
            for i,value in enumerate(values):add('secret.'+item['id']+'.'+action+'.'+str(i),action,value,'deny','secret-owner-only')
    for i,rule in enumerate(custom_denies):
        if (set(rule)!={'action','resource','effect'} or rule['effect']!='deny'
                or not all(isinstance(rule[k],str) for k in rule)):
            raise ValueError('custom clamp must be an explicit deny')
        rule=native_rule(rule,binding['home'])
        add('custom-deny-'+str(i),rule['action'],rule['resource'],'deny','custom-stricter-deny')
    return {'candidateOnly':True,'installable':False,'modelRevision':model['revision'],'modelDigest':digest(model),
            'bindingDigest':digest(binding),'binding':binding,'nativeRules':rules,'ruleManifest':manifest,
            'communication':reporting,
            'launchAcceptance':launch_acceptance(model,binding.get('launchContract'),binding.get('launchObservation')),
            'fileIdentityProtection':model['fileIdentityProtection'],
            'toolVisibilityCandidate':list(dict.fromkeys(model['nativeToolActions']['read']
                +(model['nativeToolActions']['edit'] if writes else [])
                +role_actions+([comm_action] if comm_action else [])+([milestone['action']] if milestone else [])+([checkbox['action']] if checkbox else []))),
            'run':{'requested':binding.get('runProfile'),'selected':None,'status':'production-choice-pending',
                   'classifications':model['runProfiles']},
            'limits':['Native lexical resource model, not process or symlink isolation.',
                      'Shell, grep, glob and execution remain denied; no credential adapter is invented.',
                      'Native2.0.32 hook/resource probe and installed migration are not performed.']}


def evaluate(compiled, action, requested, kind='file'):
    if action not in ('read','edit'):
        return winner(action,requested,compiled['ruleManifest'])
    target=resources(requested,compiled['binding'],kind)
    if target['external']:
        gate=winner('external_directory',target['external'],compiled['ruleManifest'])
        if gate['effect']!='allow':return gate
    return winner(action,target['resource'],compiled['ruleManifest'])


def agent_parts(text):
    if not text.startswith('---\n'):raise ValueError('unsupported agent frontmatter')
    header,body=text[4:].split('\n---\n',1)
    if header.lstrip().startswith('{'):
        fields=json.loads(header)
        return header,body,fields.get('permissions',[]),fields,None
    if re.search(r'(?m)^-',header):raise ValueError('indentless YAML sequence requires native decoder; refuse')
    if len(re.findall(r'(?m)^permissions:',header))>1:raise ValueError('duplicate permissions mapping')
    match=re.search(r'(?m)^permissions:[^\n]*(?:\n(?:[ \t]+[^\n]*\n?)*)?',header+'\n')
    if not match:return header,body,[],None,None
    value=match[0].split(':',1)[1].strip()
    if value.startswith('['):existing=json.loads(value)
    else:
        existing=[]
        for block in re.split(r'(?m)^[ \t]*- ', '\n'+value):
            if not block.strip():continue
            item={}
            for line in block.splitlines():
                if not line.strip():continue
                key,sep,value=line.strip().partition(':')
                value=value.strip()
                if not sep or key not in ('action','resource','effect') or not value:
                    raise ValueError('complex YAML permissions need the native decoder; refuse')
                if value.startswith('"'):value=json.loads(value)
                elif value.startswith("'") and value.endswith("'"):value=value[1:-1].replace("''", "'")
                elif value.startswith(('{','[','&','*','!')):raise ValueError('unsupported YAML scalar')
                item[key]=value
            if set(item)!={'action','resource','effect'}:raise ValueError('unsupported YAML rule shape')
            existing.append(item)
    return header,body,existing,None,match


def amend_agent(text, compiled):
    """Pure candidate emission, preserving body and unrelated metadata. No write."""
    header,body,existing,fields,match=agent_parts(text)
    stricter=[r for r in existing if r['effect']=='deny' and r not in compiled.get('explicitlyRetiredBaseline',[])]
    if any(native_rule(r,compiled['binding']['home']) not in compiled['nativeRules'] for r in stricter):
        raise ValueError('compile with retained custom denials before emitting')
    if fields is not None:
        fields['permissions']=compiled['nativeRules']
        return '---\n'+json.dumps(fields,separators=(',',':'))+'\n---\n'+body
    # Standard native YAML block; complex YAML must use the actual decoder in
    # future installer work, never a guessed destructive general-purpose parser.
    replacement='permissions: '+json.dumps(compiled['nativeRules'],separators=(',',':'))+'\n'
    updated=(header+'\n')[:match.start()]+replacement+(header+'\n')[match.end():] if match else header+'\n'+replacement
    return '---\n'+updated.rstrip('\n')+'\n---\n'+body


def compile_for_agent(model,binding,text,*,managed_baseline=()):
    """Baseline retirement is an EXPLICIT migration input, never inferred from '*'."""
    existing=agent_parts(text)[2]
    base=compile_policy(model,binding)
    if any(r not in existing or r.get('effect')!='deny' for r in managed_baseline):
        raise ValueError('managed baseline must identify exact existing deny rules')
    # Only recognize a complete generated prefix, not a coincidentally identical
    # single blanket rule. Unknown user denials must continue to constrain grants.
    generated_prefix=len(base['nativeRules']) if existing[:len(base['nativeRules'])]==base['nativeRules'] else 0
    clamps=[r for r in base['ruleManifest'] if r['reason']=='normalization-clamp']
    if (not generated_prefix and existing and existing[0]==base['nativeRules'][0]
            and any({k:r[k] for k in ('action','resource','effect')} in existing for r in clamps)
            and any(r['effect']=='deny' and r not in managed_baseline for r in existing)):
        raise ValueError('possible prior generated policy differs; explicit prior-generation provenance/classification required')
    stricter=[]
    for r in existing[generated_prefix:]:
        if r['effect']=='deny' and r not in managed_baseline and r not in stricter:
            stricter.append(r)
    compiled=compile_policy(model,binding,custom_denies=stricter)
    compiled['retainedCustomDenials']=stricter
    compiled['explicitlyRetiredBaseline']=list(managed_baseline)
    return compiled,amend_agent(text,compiled)


def compose_session_policy(compiled, snapshot):
    """Explicit offline snapshot only: native order is role THEN session, last match.

    Never amend the role artifact or retire either layer's rules. Snapshot identity is
    caller-declared, not authenticated native session ownership or freshness evidence.
    """
    required={'sessionID','agentID','directory','rules','rulesDigest'}
    if not isinstance(snapshot,dict) or set(snapshot)!=required:
        raise ValueError('explicit session policy snapshot fields required')
    b=compiled['binding'];comm=b.get('communication',{})
    if (snapshot['sessionID']!=comm.get('originSession') or snapshot['directory']!=b['location']
            or not isinstance(snapshot['agentID'],str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',snapshot['agentID'])):
        raise ValueError('session snapshot origin/agent/Location binding differs')
    rules=snapshot['rules']
    if not isinstance(rules,list) or len(rules)>4096:
        raise ValueError('bounded explicit session rules list required')
    for r in rules:
        if (not isinstance(r,dict) or set(r)!={'action','resource','effect'}
                or not all(isinstance(v,str) and v and '\x00' not in v and len(v)<=4096 for v in r.values())
                or r['effect'] not in ('allow','deny','ask')):
            raise ValueError('invalid session policy rule')
    if snapshot['rulesDigest']!=digest(rules):raise ValueError('session snapshot rules digest conflict')
    normalized=[native_rule(r,b['home']) for r in rules]
    manifest=[{**r,'layer':'role'} for r in compiled['ruleManifest']]+[
        {**r,'id':'session-override-'+str(i),'reason':'explicit-session-snapshot','layer':'session','snapshotIndex':i}
        for i,r in enumerate(normalized)]
    return {**compiled,'nativeRules':compiled['nativeRules']+normalized,'ruleManifest':manifest,
            'sessionPolicySnapshot':json.loads(json.dumps(snapshot)),
            'composition':'role-then-session-last-match-source-only'}


def binding_acceptance(model, compiled):
    """Lexical final-rule checks for THIS binding, not native/identity proof."""
    b=compiled['binding'];rows=[]
    def check(id,action,target,expected):
        result=evaluate(compiled,action,target)
        rows.append({'id':id,'action':action,'expected':expected,'actual':result['effect'],
                     'rule':result.get('id'),'layer':result.get('layer','role'),'pass':result['effect']==expected})
    expected=model['bindingAcceptance']
    reads=[absolute(r['path'],b['home']) for r in model['commonReads']]+b['assignedRoots']
    for i,root in enumerate(reads):check('required-read-'+str(i),'read',root+'/access-check.txt',expected['requiredRead'])
    for i,scope in enumerate(b.get('ownedWrites',[])+b.get('sharedOutputs',[])):
        check('required-write-'+str(i),'edit',scope['path']+('/access-check.txt' if scope['kind']=='directory' else ''),expected['requiredWrite'])
    for i,root in enumerate(model['protectedRoots']):
        for action in ('read','edit'):check('protected-'+str(i)+'-'+action,action,absolute(root['path'],b['home'])+'/access-check.txt',expected['protected'])
    for item in model['protectedFiles']:
        target=absolute(item['path'],b['home']) if 'path' in item else b['location']+'/'+item['pattern'].replace('*','access-check')
        for action in ('read','edit'):check('protected-file-'+item['id']+'-'+action,action,target,expected['protected'])
    outside='/access-unassigned-'+compiled['bindingDigest'][:16]+'/check.txt'
    for action in ('read','edit'):check('unassigned-'+action,action,outside,expected['protected'])
    for case in model['matrix']:
        if case.get('dimension'):continue
        if case.get('expect')!='deny' or case.get('id') in ('shared-not-output','outside-write','home-unassigned'):continue
        target=case.get('path',case.get('resource','')).replace('$HOME',b['home']).replace('$PROJECT',b['location'])
        check(case['id'],case['action'],target,'deny')
    comm=b.get('communication',{});transport=model['communicationTransports'].get(comm.get('transport'),{})
    if transport.get('action'):check('reporting-action',transport['action'],'*',expected['reporting'])
    if comm.get('transport')=='chief-inbox':
        check('reporting-pointer','read',comm['chiefPointer'],expected['reporting'])
        check('reporting-output','edit',comm['inboxOutput'],expected['reporting'])
    if b.get('ownMilestone'):
        cap=model['nativeCapabilities']['ownMilestone']
        check('milestone-own-action',cap['action'],cap['resource'],'allow')
        check('milestone-foreign-resource',cap['action'],'foreign','deny')
    if b.get('planCheckbox'):
        cap=model['nativeCapabilities']['planCheckbox']
        check('checkbox-own-action',cap['action'],'own','allow')
        check('checkbox-foreign-resource',cap['action'],'foreign','deny')
    if b.get('projectPlans'):
        for i,file in enumerate(b['projectPlans']['files']):
            for action in ('read','edit'):check('own-plan-'+str(i)+'-'+action,action,file,'allow')
        root=b['home']+'/.config/openchamber/projects/'
        check('foreign-plan','edit',root+'foreign/plans/fixture.md','deny')
        check('project-metadata','edit',path.dirname(b['projectPlans']['root'])+'/context.json','deny')
    launch=compiled['launchAcceptance']
    if launch['status']!='not-required':
        rows.append({'id':'declared-launcher-provenance','expected':'verified','actual':launch['status'],'pass':False})
    snapshot=compiled.get('sessionPolicySnapshot')
    if snapshot is not None:
        role_only={**compiled,'ruleManifest':[r for r in compiled['ruleManifest'] if r['layer']=='role']}
        for i,raw in enumerate(snapshot['rules']):
            r=native_rule(raw,b['home'])
            # Literal session grants can name a denied file absent from generic probes.
            # Evaluate final ordering, so a later restoring deny still passes.
            if (r['effect']=='allow' and r['action'] in ('read','edit')
                    and not any(c in r['resource'] for c in '*?')
                    and evaluate(role_only,r['action'],r['resource'])['effect']=='deny'):
                check('session-literal-forbidden-'+str(i),r['action'],r['resource'],expected['protected'])
    session_summary=({'status':'explicit-snapshot-evaluated','sessionID':snapshot['sessionID'],
        'agentID':snapshot['agentID'],'directory':snapshot['directory'],'rulesDigest':snapshot['rulesDigest'],
        'snapshotDigest':digest(snapshot),'ruleCount':len(snapshot['rules']),'nativeIdentityAndFreshness':'unverified'}
        if snapshot is not None else 'not-evaluated')
    return {'bindingID':b['id'],'nativeProof':False,'sessionOverrides':session_summary,
            'fileIdentityProtection':model['fileIdentityProtection'],'rows':rows,
            'passed':sum(r['pass'] for r in rows),'total':len(rows)}


def fixture_binding(model,role):
    b={'id':'fixture-'+role,'role':role,'home':'/fixture/home','location':'/fixture/project','projectRoot':'/fixture/project',
       'assignedRoots':['/fixture/project'],'ownedWrites':[],'sharedOutputs':[],'runProfile':None}
    if model['roles'][role]['writes']:
        b['ownedWrites']=[{'path':'/fixture/project/owned/result.md','kind':'file'}]
        b['sharedOutputs']=[{'path':'/fixture/home/.chief-of-staff/handoff/result.md','kind':'file'}]
    mode=model['roles'][role]['communication'][0]
    b['communication']={'transport':mode,'originSession':'ses_fixture'+role,'originDirectory':b['location']}
    if model['communicationTransports'][mode]['target']=='current-chief':
        b['communication']['chiefPointer']=absolute(model['currentChiefPointer'],b['home'])
    if mode=='parent-return':b['communication'].update(parentSession='ses_fixtureparent',parentDirectory='/fixture/parent')
    return b


def matrix(model):
    results=[]
    for role,profile in model['roles'].items():
        b=fixture_binding(model,role)
        if role=='lead':b['ownMilestone']={'sessionID':'ses_fixturelead','agentID':'lead','directory':b['location']}
        if role=='lead':b['planCheckbox']={'sessionID':b['communication']['originSession'],'agentID':'lead','directory':b['location'],'planIDs':['plan-own']}
        plan_root=b['home']+'/.config/openchamber/projects/fixture-own/plans'
        if role=='lead':b['projectPlans']={'sessionID':b['communication']['originSession'],'directory':b['location'],
            'projectId':'fixture-own','root':plan_root,'files':[plan_root+'/approved.md'],
            'evidenceDigest':digest('synthetic fixture, no native authority'),'status':model['projectPlans']['status']}
        compiled=compile_policy(model,b)
        for case in model['matrix']:
            dimension=case.get('dimension')
            if dimension=='leadMemory':
                from lead_memory import memory_rules
                expected=case.get('expect') or case['expectByRole'].get(role,case['expectByRole']['default'])
                rules=[{'action':'*','resource':'*','effect':'deny'}]
                plan=b['home']+'/.config/openchamber/projects/own/plans/approved.md'
                if role=='lead':rules+=memory_rules(model,b['location'],[plan])
                target={'plan':plan,'foreign':'/foreign/LEAD.md','metadata':path.dirname(path.dirname(plan))+'/context.json',
                        'milestone':'own'}.get(case['scenario'],case['scenario'])
                found=winner('docket_milestone' if case['scenario']=='milestone' else 'edit',target,rules)['effect']
                results.append({'role':role,'case':case['id'],'expected':expected,'actual':found,'nativeProof':False,'pass':found==expected});continue
            if dimension=='planCheckbox':
                expected=case.get('expect') or case['expectByRole'].get(role,case['expectByRole']['default'])
                caller={'sessionID':b['communication']['originSession'],'agentID':'lead','directory':b['location']}
                if case['scenario']=='caller':caller['sessionID']='ses_foreign'
                found=checkbox_admission(model,b,caller,'foreign' if case['scenario']=='foreign' else 'plan-own')
                results.append({'role':role,'case':case['id'],'expected':expected,'actual':found,'nativeProof':False,'pass':expected==found});continue
            if dimension=='projectPlan':
                expected=case.get('expect') or case['expectByRole'].get(role,case['expectByRole']['default'])
                target={'own':plan_root+'/approved.md','foreign':path.dirname(path.dirname(plan_root))+'/foreign/plans/approved.md',
                        'metadata':path.dirname(plan_root)+'/context.json','unlisted':plan_root+'/unlisted.md'}[case['scenario']]
                found=evaluate(compiled,'edit',target)
                results.append({'role':role,'case':case['id'],'expected':expected,'actual':found['effect'],
                                'nativeProof':False,'pass':expected==found['effect']});continue
            if dimension in ('milestone','launcher'):
                expected=case.get('expect') or case['expectByRole'].get(role,case['expectByRole']['default'])
                if dimension=='milestone':
                    caller=b.get('ownMilestone',{'sessionID':'ses_fixture'+role,'agentID':role,'directory':b['location']})
                    enrollment={'sessionID':caller['sessionID'],'directory':caller['directory']}
                    if case['scenario']=='foreign':caller={**caller,'sessionID':'ses_foreign'}
                    if case['scenario']=='absent':enrollment=None
                    found=milestone_admission(model,b,caller,enrollment)
                else:
                    contract={'launcherID':'fixture-launcher','sessionID':'ses_fixture','agentID':role,
                        'model':{'providerID':'fixture','modelID':'model','variant':'medium'},'directory':b['location'],
                        'sessionPolicyDigest':digest([]),'bindingDigest':digest(b)}
                    observation={**contract,'launched':True,'receipt':'unverified-caller-text'}
                    if case['scenario']=='generic':observation['method']='generic-session'
                    if case['scenario']=='mismatch':observation['agentID']='other'
                    if case['scenario']=='undeclared':contract=observation=None
                    found=launch_acceptance(model,contract,observation)['status']
                results.append({'role':role,'case':case['id'],'expected':expected,'actual':found,'nativeProof':False,'pass':found==expected});continue
            if case.get('dimension')=='communication':
                found=compiled['communication']['status'];results.append({'role':role,'case':case['id'],
                    'expected':case['expect'],'actual':found,'nativeProof':False,'pass':found==case['expect']});continue
            target=case.get('path',case.get('resource','')).replace('$HOME',b['home']).replace('$PROJECT',b['projectRoot'])
            expected=case.get('expect') or case['expectByWrites'][str(profile['writes']).lower()]
            found=evaluate(compiled,case['action'],target)
            results.append({'role':role,'case':case['id'],'expected':expected,'actual':found['effect'],
                            'rule':found.get('id'),'reason':found.get('reason'),'pass':expected==found['effect']})
    return results


def matrix_document(model):
    rows=matrix(model)
    return {'candidateOnly':True,'installable':False,'nativeProof':False,
            'modelRevision':model['revision'],'modelDigest':digest(model),
            'cases':[c['id'] for c in model['matrix']],
            'roleResults':{role:[r['actual'] for r in rows if r['role']==role] for role in model['roles']},
            'passed':sum(r['pass'] for r in rows),'total':len(rows)}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',type=Path,default=MODEL);p.add_argument('--binding',type=Path);p.add_argument('--matrix',action='store_true');a=p.parse_args();model=json.loads(a.model.read_text())
    if a.matrix:
        result=matrix_document(model);print(json.dumps(result,indent=2));raise SystemExit(0 if result['passed']==result['total'] else 1)
    if not a.binding:p.error('--binding or --matrix required; no live discovery or install mode')
    print(json.dumps(compile_policy(model,json.loads(a.binding.read_text())),indent=2))
