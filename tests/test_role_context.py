import copy
import sys
import unittest
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from role_context import append_denials, compile_denials, amend_header, prepare, apply, rollback, sha


class ContextCompilerTest(unittest.TestCase):
    def setUp(self):
        self.registry = {'tools': ['read', 'opencode_list_mcp_resources', 'websearch'],
                         'skills': ['checkpoint', 'shape', 'unrelated-skill']}
        self.allow = {'tools': ['read', 'opencode_list_mcp_resources'], 'skills': ['checkpoint']}

    def test_exact_denials_and_preserved_rule_order(self):
        existing = [{'action': 'edit', 'resource': '*', 'effect': 'deny'},
                    {'action': 'read', 'resource': '*', 'effect': 'ask'}]
        before = copy.deepcopy((existing, self.registry, self.allow))
        result = append_denials(existing, 'lead', self.registry, self.allow)
        self.assertEqual(result[:2], existing)
        self.assertEqual(result[2:], [
            {'action': 'websearch', 'resource': '*', 'effect': 'deny'},
            {'action': 'skill', 'resource': 'shape', 'effect': 'deny'},
            {'action': 'skill', 'resource': 'unrelated-skill', 'effect': 'deny'}])
        self.assertEqual((existing, self.registry, self.allow), before)
        self.assertEqual(append_denials(result, 'lead', self.registry, self.allow), result)

    def test_rejects_duplicate_types_patterns_and_missing_dependencies(self):
        for registry in [None, {'tools': [], 'skills': []},
                         {'tools': ['read', 'read'], 'skills': []},
                         {'tools': [3], 'skills': []},
                         {'tools': ['opencode_*'], 'skills': []},
                         {'tools': ['read'], 'skills': ['checkpoint']},
                         {'tools': ['read'], 'skills': [], 'complete': True}]:
            with self.subTest(registry=registry), self.assertRaises(ValueError):
                compile_denials('lead', registry, self.allow)
        with self.assertRaises(ValueError):
            compile_denials('build', self.registry, self.allow)

    def test_dispatcher_and_chief_constraints(self):
        registry = {'tools': ['heartbeat_resolve', 'execute'], 'skills': ['checkpoint']}
        self.assertEqual(compile_denials('dispatcher', registry,
            {'tools': ['heartbeat_resolve'], 'skills': []})['dispatcher'], [
                {'action': 'execute', 'resource': '*', 'effect': 'deny'},
                {'action': 'skill', 'resource': 'checkpoint', 'effect': 'deny'}])
        with self.assertRaises(ValueError):
            compile_denials('dispatcher', registry, {'tools': ['execute'], 'skills': []})
        with self.assertRaises(ValueError):
            compile_denials('chief', self.registry,
                            {'tools': ['read'], 'skills': ['unrelated-skill']})

    def test_writer_exact_dependencies_are_not_guessed(self):
        with self.assertRaises(ValueError):
            compile_denials('writer', self.registry,
                            {'tools': ['actual_writer_tool'], 'skills': ['checkpoint']})

    def test_edit_aliases_never_become_fictitious_or_blanket_denies(self):
        registry = {'tools': ['read', 'patch', 'write', 'edit', 'opencode_worktree_remove'],
                    'skills': ['checkpoint']}
        allow = {'tools': ['read', 'patch'], 'skills': ['checkpoint']}
        existing = [{'action': 'edit', 'resource': '*', 'effect': 'deny'},
                    {'action': 'edit', 'resource': '/own/LEAD.md', 'effect': 'allow'}]
        self.assertEqual(compile_denials('lead', registry, allow), {'lead': []})
        self.assertEqual(append_denials(existing, 'lead', registry, allow), existing)
        with self.assertRaises(ValueError):
            compile_denials('lead', registry, allow,
                            tool_actions={'opencode_worktree_remove': 'opencode_worktree_remove'})
        with self.assertRaises(ValueError):
            append_denials([{'action':'opencode_worktree_remove','resource':'*','effect':'deny'}],
                           'lead', registry, allow)

    def test_verified_mcp_action_shared_action_and_direct_only(self):
        registry = {'tools': ['read', 'docs_search', 'custom_read', 'heartbeat_close'],
                    'skills': ['checkpoint']}
        allow = {'tools': ['read'], 'skills': ['checkpoint']}
        with self.assertRaises(ValueError):
            compile_denials('lead', registry, allow)
        self.assertEqual(compile_denials('lead', registry, allow, tool_actions={
            'docs_search':'docs_search', 'custom_read':'read', 'heartbeat_close':None}),
            {'lead':[{'action':'docs_search','resource':'*','effect':'deny'}]})
        with self.assertRaises(ValueError):
            compile_denials('lead', registry, allow, tool_actions=[])

    def test_header_apply_and_exact_rollback(self):
        text = ('---\ndescription: Keep exactly.\nmodel: provider/model#medium\n'
                'permissions: [{"action":"edit","resource":"*","effect":"deny"}]\n'
                'hidden: false\n---\n<!-- managed by chief-of-staff/install.sh -->\nBody.\n')
        after = amend_header(text, 'lead', self.registry, self.allow)
        self.assertTrue(after.startswith('---\ndescription: Keep exactly.\nmodel: provider/model#medium\n'))
        self.assertTrue(after.endswith('hidden: false\n---\n<!-- managed by chief-of-staff/install.sh -->\nBody.\n'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / 'agent.md'; path.write_text(text)
            manifest = prepare(path, 'lead', self.registry, self.allow, sha(text.encode()))
            receipt = apply(manifest, path.parent / 'before.bin')
            self.assertEqual(path.read_text(), after)
            path.write_text(after + 'owner work')
            with self.assertRaises(ValueError):
                rollback(receipt)
            path.write_text(after)
            rollback(receipt)
            self.assertEqual(path.read_text(), text)


if __name__ == '__main__':
    unittest.main()
