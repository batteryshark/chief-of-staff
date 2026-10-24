"""Bundled packages install standalone; no home writes or skill execution."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import interface_skills as installer
import role_contract
import lean_roles


class InterfaceSkillsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name).resolve()

    def test_self_contained_license_complete_install_idempotent_and_uninstall(self):
        hosts=['opencode','claude','codex']
        installer.apply('check',hosts,self.home)
        self.assertFalse(list(self.home.iterdir()))
        installer.apply('install',hosts,self.home); installer.apply('install',hosts,self.home)
        for source,target in installer.targets(hosts,self.home):
            self.assertIn('MIT License',(target/'LICENSE').read_text())
            self.assertTrue((target/'SKILL.md').is_file()); self.assertTrue((target/'references/cli-tui.md').is_file())
            self.assertTrue(list((target/'agents').glob('*.md')))
            self.assertTrue(list((target/'scripts').glob('*.py')))
            self.assertTrue(os.access(target/'bin'/target.name,os.X_OK))
            actual=installer.inventory(target); actual.pop(installer.RECEIPT)
            self.assertEqual(actual,installer.inventory(source))
        installer.apply('uninstall',hosts,self.home)
        self.assertFalse(any(target.exists() for _,target in installer.targets(hosts,self.home)))

    def test_foreign_modified_linked_and_extra_files_refused_before_any_bundle_change(self):
        target=self.home/'.config/opencode/skills/norman'
        target.mkdir(parents=True); (target/'SKILL.md').write_text('foreign')
        with self.assertRaises(ValueError): installer.apply('install',['opencode'],self.home)
        self.assertEqual((target/'SKILL.md').read_text(),'foreign'); self.assertFalse(target.with_name('norman-audit').exists())
        (target/'SKILL.md').unlink(); target.rmdir()
        target.symlink_to(self.home/'elsewhere')
        with self.assertRaises(ValueError): installer.apply('install',['opencode'],self.home)
        target.unlink()
        installer.apply('install',['opencode'],self.home)
        (target/'extra.txt').write_text('foreign')
        for mode in ('install','uninstall'):
            with self.assertRaises(ValueError): installer.apply(mode,['opencode'],self.home)
        self.assertTrue((target/'SKILL.md').exists())
        (target/'extra.txt').unlink(); (target/'references/cli-tui.md').write_text('changed')
        with self.assertRaises(ValueError): installer.apply('uninstall',['opencode'],self.home)

    def test_lead_manifest_worker_discovery_chief_exclusion_and_prompt_budget(self):
        code="""import {skills,matches,roleFor} from './services/role-context.mjs';
console.log(JSON.stringify({lead:['norman','norman-audit'].every(n=>matches(n,skills.lead)),
chief:['norman','norman-audit'].some(n=>matches(n,skills.chief)),worker:roleFor('build')}));"""
        result=subprocess.run(['node','--input-type=module','-e',code],cwd=ROOT,capture_output=True,text=True,check=True)
        data=json.loads(result.stdout); self.assertTrue(data['lead']); self.assertFalse(data['chief']); self.assertNotIn('worker',data)
        permissions=role_contract.permissions('chief',str(self.home),str(self.home/'chief'))
        for name in installer.NAMES:
            self.assertIn({'action':'skill','resource':name,'effect':'deny'},permissions)
        source=(ROOT/'kits/reset/lead.md').read_text()
        self.assertIn('norman build, norman-audit before acceptance',source)
        self.assertLessEqual(len(source.encode()),3076); self.assertLessEqual(len(source.splitlines()),36)
        brief=(ROOT/'kits/reset/skills/worker-dispatch/SKILL.md').read_text()
        self.assertIn('UI work: norman while building, norman-audit before acceptance',brief)
        lean_roles.body('lead',str(self.home))
        install=(ROOT/'install.sh').read_text()
        self.assertIn('interface_skills.py" check',install); self.assertIn('interface_skills.py" "$mode"',install)


if __name__=='__main__': unittest.main()
