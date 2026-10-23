import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from access_policy import agent_parts,winner
from lead_memory import LEGACY,memory_rules,repair_role

class MemoryRepair(unittest.TestCase):
    def setUp(self):
        self.model=json.loads((ROOT/'access/model.json').read_text());self.location='/fixture/own'
        self.plan='/fixture/home/.config/openchamber/projects/own/plans/approved.md'
        self.extra=[{'action':'shell','resource':'git push*','effect':'ask'},
                    {'action':'edit','resource':'private/*','effect':'deny'},
                    {'action':'edit','resource':'independent/*','effect':'allow'}]
        self.text='---\n'+json.dumps({'description':'custom prose','model':'keep','permissions':LEGACY+self.extra})+'\n---\nUnchanged holds/body.\n'

    def test_narrow_generated_repair_and_session_precedence(self):
        emitted,rules=repair_role(self.model,self.text,self.location,[self.plan],LEGACY)
        self.assertEqual(agent_parts(emitted)[1],agent_parts(self.text)[1]);self.assertEqual(agent_parts(emitted)[3]['model'],'keep')
        for resource in ['LEAD.md','PROJECT.md','lead/x/y.md','/fixture/own/LEAD.md','/fixture/own/PROJECT.md',self.plan]:
            self.assertEqual(winner('edit',resource,rules)['effect'],'allow')
        for resource in ['/foreign/LEAD.md','../foreign/lead/x.md','/fixture/own/src/main.py',self.plan+'x',self.plan.replace('/own/','/foreign/'),'lead/private.env',self.plan.rsplit('/plans/',1)[0]+'/context.json']:
            self.assertEqual(winner('edit',resource,rules)['effect'],'deny')
        self.assertEqual(rules[-len(self.extra):],self.extra)
        self.assertEqual(winner('edit','independent/x',rules)['effect'],'allow')
        self.assertEqual(winner('edit','LEAD.md',rules+[{'action':'edit','resource':'LEAD.md','effect':'deny'}])['effect'],'deny')
        self.assertEqual(winner('edit','LEAD.md',rules+[{'action':'edit','resource':'LEAD.md','effect':'allow'}])['effect'],'allow')

    def test_unknown_generated_prefix_and_conflicting_custom_deny_refuse(self):
        with self.assertRaises(ValueError):repair_role(self.model,self.text,self.location,[self.plan],[])
        text='---\n'+json.dumps({'permissions':LEGACY+[{'action':'edit','resource':'LEAD.md','effect':'deny'}]})+'\n---\nKeep\n'
        with self.assertRaises(ValueError):repair_role(self.model,text,self.location,[self.plan],LEGACY)

    def test_no_global_external_or_write_grant(self):
        rules=memory_rules(self.model,self.location,[self.plan])
        self.assertFalse(any(r['effect']=='allow' and r['resource']=='*' for r in rules))
        self.assertEqual([r['resource'] for r in rules if r['action']=='external_directory'],[self.plan.rsplit('/',1)[0]+'/*'])
        self.assertEqual(winner('docket_milestone','own',rules)['effect'],'allow')

if __name__=='__main__':unittest.main()
