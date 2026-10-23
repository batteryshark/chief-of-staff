"""Narrow migration repair, independent of the unselected general access rollout.
All binding paths come from trusted installer discovery; never tool arguments.
"""
import json
from pathlib import PurePosixPath as Path
from pathlib import Path as LocalPath
from access_policy import absolute, agent_parts, amend_agent, wildcard, winner

LEGACY=[{'action':'edit','resource':r,'effect':e} for r,e in
        [('*','deny'),('PROJECT.md','allow'),('LEAD.md','allow'),('*/LEAD.md','allow'),('lead/*','allow'),('*/lead/*','allow')]]

def memory_rules(model,location,plan_files):
    absolute(location)
    rules=[]
    def add(action,resource,effect='allow'):rules.append(dict(action=action,resource=resource,effect=effect))
    for name in model['leadMemory']['files']:
        for target in (name,location+'/'+name):add('edit',target)
    for name in model['leadMemory']['directories']:
        for target in (name+'/*',location+'/'+name+'/*'):add('edit',target)
    for file in plan_files:
        absolute(file)
        if not file.endswith('.md') or Path(file).parent.name!='plans':raise ValueError('exact listed plan file required')
        add('external_directory',str(Path(file).parent)+'/*');add('edit',file)
    add(model['leadMemory']['milestoneAction'],'own')
    # Secret-pattern clamps apply after own lead/**. Never turn that directory
    # into an env/key exception. Outside scopes retain their existing rules.
    for file in model['protectedFiles']:
        if 'pattern' in file:add('edit',file['pattern'],'deny')
    return list({json.dumps(r,sort_keys=True):r for r in rules}.values())

def repair_role(model,text,location,plan_files,verified_generated_rules):
    existing=agent_parts(text)[2]
    if verified_generated_rules[:len(LEGACY)]!=LEGACY or existing[:len(LEGACY)]!=LEGACY:
        raise ValueError('original migration receipt prefix required; custom block not retired')
    # Keep the generated default deny, remove only its imprecise wildcard allows.
    # Preserve EVERY remaining rule, including asks and unrelated grants/denials.
    original_rest=existing[len(LEGACY):]
    grants=memory_rules(model,location,plan_files)
    for rule in original_rest:
        if rule['effect']!='allow' and any(winner(g['action'],g['resource'],[rule])==rule for g in grants if g['effect']=='allow'):
            raise ValueError('independent custom constraint conflicts; no widening')
    rules=[LEGACY[0],*grants,*original_rest]
    compiled={'binding':{'home':str(LocalPath.home())},'nativeRules':rules,'explicitlyRetiredBaseline':[]}
    return amend_agent(text,compiled),rules
