"""Scoped bundle fixtures only; no runtime/service/scheduler calls."""
import copy
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SRC = Path(__file__).resolve().parent.parent


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.domain = self.home / '.chiefs/example'
        self.env = {**os.environ, 'HOME':str(self.home), 'CHIEF_BRIEF_DIR':str(self.home / '.chief-of-staff'),
                    'PYTHONDONTWRITEBYTECODE':'1', 'NPM_CONFIG_OFFLINE':'true', 'NPM_CONFIG_UPDATE_NOTIFIER':'false'}
        self.profile = json.loads((SRC / 'profiles/example/profile.json').read_text())

    def run_install(self, *args, profile='example'):
        if isinstance(profile, dict):
            file = self.root / 'profile.json'
            file.write_text(json.dumps(profile))
            profile = str(file)
        return subprocess.run(['bash',str(SRC / 'install.sh'),'--profile',profile,*args],
                              env=self.env,capture_output=True,text=True,timeout=120)

    def snapshot(self):
        return {str(p.relative_to(self.home)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.home.rglob('*') if p.is_file() and not p.is_symlink()}

    def test_install_coexists_with_default_and_standalone(self):
        before = subprocess.run(['bash',str(SRC / 'install.sh')], env=self.env,capture_output=True,text=True,timeout=120)
        self.assertEqual(before.returncode,0,before.stderr)
        baseline = self.snapshot()
        result = self.run_install()
        self.assertEqual(result.returncode,0,result.stderr)
        for file,digest in baseline.items():
            self.assertEqual(self.snapshot()[file],digest)
        lead = (self.domain / '.opencode/agents/example-lead.md').read_text()
        for phrase in ('source ledger','conflicting evidence',str(self.domain / 'chief.json'),'example-checkpoint'):
            self.assertIn(phrase,lead)
        self.assertNotIn('see ' + str(self.home / '.chief-of-staff/chief.json'),lead)
        self.assertNotIn('Re-read `' + str(self.home / '.chief-of-staff/chief.json'),lead)
        self.assertFalse((self.domain / 'models.md').exists())
        config = self.root / 'independent.json'
        config.write_text(json.dumps(dict(version=1,agent='independent-lead',packs=['engineering'],owner=dict(mode='principal',style='Short outcomes.'))))
        result = subprocess.run(['bash',str(SRC/'install.sh'),'--lead-config',str(config)],env=self.env,capture_output=True,text=True,timeout=120)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.run_install('--uninstall').returncode,0)
        for file,digest in baseline.items(): self.assertEqual(self.snapshot()[file],digest)
        self.assertTrue((self.home / '.config/opencode/agents/independent-lead.md').is_file())

    def test_scoped_workflows_fresh_home_names_and_native_policy(self):
        result = self.run_install()
        self.assertEqual(result.returncode,0,result.stderr)
        root = self.domain / '.opencode'
        shape = (root / 'commands/example-shape.md').read_text()
        checkpoint = (root / 'commands/example-checkpoint.md').read_text()
        self.assertIn('agent: example-chief',shape)
        for phrase in ('agent `example-chief`', 'agent `example-lead`', str(self.domain), 'example-checkpoint','nest: false'):
            self.assertIn(phrase,checkpoint)
        self.assertNotIn('agent `chief-of-staff`',checkpoint)
        for role in ('chief','lead','worker'):
            text=(root / f'agents/example-{role}.md').read_text()
            header=json.loads(text.split('---')[1])
            self.assertEqual(header['permissions'][0],dict(action='*',resource='*',effect='deny'))
            self.assertIn(dict(action='webfetch',resource='*',effect='allow'),header['permissions'])
            self.assertIn(dict(action='websearch',resource='*',effect='allow'),header['permissions'])
            self.assertNotIn('tools',header)
            self.assertNotIn('{{',text)
        self.assertTrue((root/'plugins/chief-domain/index.ts').is_file())
        self.assertFalse((self.home / '.config/opencode/opencode.json').exists())
        self.assertFalse((self.home / '.local').exists())

    def test_shared_references_and_fleet_are_in_both_prompts(self):
        self.assertEqual(self.run_install().returncode,0)
        for role in ('chief','lead'):
            text=(self.domain/f'.opencode/agents/example-{role}.md').read_text()
            for phrase in (str(self.home/'.chief-of-staff/models.md'),str(self.home/'.chief-of-staff/runway'),
                           'AGENT_USAGE.md','fleet add','fleet adopt','health probe and group','not\npermission to install'):
                self.assertIn(phrase,text)
        registry=json.loads((self.home/'.config/chief-of-staff/domains.json').read_text())
        self.assertEqual({r['id'] for r in registry['domains']},{'technical','example'})
        self.assertNotIn('session',str(registry))

    def test_reinstall_private_seeds_inventory_and_rollback(self):
        self.assertEqual(self.run_install().returncode,0)
        inventory=json.loads((self.domain/'.kit-install.json').read_text())
        self.assertEqual(len(inventory['owned']),10)
        for name in ('brief.md','principal.md','open.md','chief.json'):
            (self.domain/name).write_text('private fixture '+name)
        self.assertEqual(self.run_install().returncode,0)
        for name in ('brief.md','principal.md','open.md','chief.json'):
            self.assertEqual((self.domain/name).read_text(),'private fixture '+name)
        self.assertEqual(self.run_install('--uninstall').returncode,0)
        self.assertFalse((self.domain/'.kit-install.json').exists())
        for target in inventory['owned']: self.assertFalse((self.home/target).exists())
        self.assertTrue((self.domain/'principal.md').exists())
        registry=json.loads((self.home/'.config/chief-of-staff/domains.json').read_text())
        self.assertEqual([r['id'] for r in registry['domains']],['technical'])

    def test_schema_invalid_names_hosts_and_scope_fail_before_writes(self):
        bad=[{**self.profile,'version':True},{**self.profile,'home':'.chief-of-staff'},
             {**self.profile,'chief_agent':'chief-of-staff'}, {**self.profile,'chief_agent':'example-lead'},
             {**self.profile,'chief_agent':'example-checkpoint'}, {**self.profile,'id':'technical'},
             {**self.profile,'adapter':'claude-sandbox'},{**self.profile,'lead_packs':['unknown']},
             {**self.profile,'extra':'ignored'},{**self.profile,'tone':'{{INJECT}}'}]
        for config in bad:
            result=self.run_install(profile=config)
            self.assertNotEqual(result.returncode,0,result.stdout)
            self.assertEqual(list(self.home.iterdir()),[])
        for args in (('claude',),('codex',),('bin',),('home',),('--routing',)):
            self.assertNotEqual(self.run_install(*args).returncode,0)
            self.assertEqual(list(self.home.iterdir()),[])

    def test_another_domain_uses_same_kit_without_forks(self):
        self.assertEqual(self.run_install().returncode,0)
        custom={**self.profile,'id':'study','home':'.chiefs/study','chief_agent':'study-chief','lead_agent':'study-lead','worker_agent':'study-worker', 'lead_packs':['research'], 'remit':'Review public literature only.','tone':'Concise evidence first.'}
        self.assertEqual(self.run_install(profile=custom).returncode,0)
        self.assertTrue((self.home/'.chiefs/study/.opencode/agents/study-chief.md').exists())
        self.assertTrue((self.domain/'.opencode/agents/example-chief.md').exists())
        self.assertEqual(self.run_install('--uninstall',profile=custom).returncode,0)
        self.assertTrue((self.domain/'.kit-install.json').exists())

    def test_last_conflict_and_modified_owned_file_have_no_partial_mutation(self):
        last=self.domain/'AGENTS.md';last.parent.mkdir(parents=True)
        last.write_text('user work')
        before=self.snapshot()
        self.assertNotEqual(self.run_install().returncode,0)
        self.assertEqual(before,self.snapshot())
        last.unlink()
        self.assertEqual(self.run_install().returncode,0)
        last.write_text(last.read_text()+'\nuser edit')
        before=self.snapshot()
        self.assertNotEqual(self.run_install('--uninstall').returncode,0)
        self.assertEqual(before,self.snapshot())

    def test_symlink_ancestors_refuse_install_uninstall_print_dry(self):
        self.assertEqual(self.run_install().returncode,0)
        linked=self.domain/'.opencode/skills/example-checkpoint'
        outside=self.root/'linked-skill';linked.rename(outside);linked.symlink_to(outside,target_is_directory=True)
        before=self.snapshot(); external=(outside/'SKILL.md').read_bytes()
        for args in ((),('--uninstall',),('--print',),('--dry-run',)):
            result=self.run_install(*args)
            self.assertNotEqual(result.returncode,0,result.stdout)
            self.assertIn('symlink',result.stderr)
            self.assertEqual(before,self.snapshot())
            self.assertEqual(external,(outside/'SKILL.md').read_bytes())

    def test_directory_conflict_and_scope_change_fail_before_changes(self):
        self.assertEqual(self.run_install().returncode,0)
        before=self.snapshot()
        self.assertNotEqual(self.run_install(profile={**self.profile,'lead_agent':'example-new-lead'}).returncode,0)
        self.assertEqual(before,self.snapshot())
        directory=self.home/'.config/chief-of-staff/domains.json'
        data=json.loads(directory.read_text());data['domains'].append(copy.deepcopy(data['domains'][0]));directory.write_text(json.dumps(data))
        before=self.snapshot()
        self.assertNotEqual(self.run_install().returncode,0)
        self.assertEqual(before,self.snapshot())
        data['domains'].pop();data['version']=True;directory.write_text(json.dumps(data))
        before=self.snapshot()
        self.assertNotEqual(self.run_install().returncode,0)
        self.assertEqual(before,self.snapshot())

    def test_explicit_technical_selection_and_brief_override_match_default(self):
        default=subprocess.run(['bash',str(SRC/'install.sh'),'--print'],env=self.env,capture_output=True,text=True,timeout=120)
        selected=self.run_install('--print',profile='technical')
        self.assertEqual(default.returncode,0,default.stderr)
        self.assertEqual(default.stdout,selected.stdout)
        self.assertIn(str(self.home/'.chief-of-staff'),selected.stdout)

    def test_goal_binding_is_optional_host_only_and_never_installed(self):
        self.assertEqual(self.run_install().returncode, 0)
        plugin = (self.domain / '.opencode/plugins/chief-domain/index.ts').read_text()
        binding = self.home / '.config/chief-of-staff/goal-bindings/example/binding.json'
        self.assertIn('"goal_binding": "' + str(binding) + '"', plugin)
        self.assertFalse(binding.parent.exists())
        self.assertNotIn('Authorization', plugin)
        self.assertNotIn('desktopLocalClientToken', plugin)
        for role in ('chief', 'lead', 'worker'):
            text = (self.domain / f'.opencode/agents/example-{role}.md').read_text()
            rules = json.loads(text.split('---')[1])['permissions']
            for action in ('read', 'edit', 'external_directory'):
                matches = [r['effect'] for r in rules if fnmatch.fnmatchcase(action, r['action']) and fnmatch.fnmatchcase(str(binding), r['resource'])]
                self.assertEqual(matches[-1], 'deny')

    def test_fresh_lead_checkpoint_and_prompt_retain_goal_bridge(self):
        self.assertEqual(self.run_install().returncode, 0)
        for name in ('.opencode/agents/example-lead.md', '.opencode/commands/example-checkpoint.md', '.opencode/skills/example-checkpoint/SKILL.md'):
            text = (self.domain / name).read_text()
            self.assertIn('domain_lead_start', text)
            self.assertIn('replacement: true', text)
            self.assertIn('SAME outcome', text)

    def test_role_plugin_actions_and_all_managed_instruction_surfaces(self):
        self.assertEqual(self.run_install().returncode,0)
        inventory=json.loads((self.domain/'.kit-install.json').read_text())
        for role in ('chief','lead','worker'):
            text=(self.domain/f'.opencode/agents/example-{role}.md').read_text()
            rules=json.loads(text.split('---')[1])['permissions']
            def effect(action,resource):
                return [r['effect'] for r in rules if fnmatch.fnmatchcase(action,r['action']) and fnmatch.fnmatchcase(resource,r['resource'])][-1]
            self.assertEqual(effect('domain_identity','*'),'allow')
            self.assertEqual(effect('domain_a2a_send','*'),'allow')
            self.assertEqual(effect('domain_a2a_create','*'),'deny' if role=='worker' else 'allow')
            self.assertEqual(effect('domain_lead_start','*'),'deny' if role=='worker' else 'allow')
            for action in ('shell','execute','openchamber','a2a_create','a2a_send'):
                self.assertEqual(effect(action,'*'),'deny')
            for owned in inventory['owned']:
                self.assertEqual(effect('edit',str(self.home/owned)),'deny')
        chief_rules=json.loads((self.domain/'.opencode/agents/example-chief.md').read_text().split('---')[1])['permissions']
        self.assertEqual([r['effect'] for r in chief_rules if fnmatch.fnmatchcase('edit',r['action']) and fnmatch.fnmatchcase('chief.json',r['resource'])][-1],'allow')


if __name__=='__main__': unittest.main()
