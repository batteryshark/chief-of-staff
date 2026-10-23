"""Small offline fixtures for native Note selection, freshness and fallback."""
import base64
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import contextlib
import io
import types

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('render', ROOT / 'scripts/render.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
p = types.ModuleType('portfolio')
exec(compile(r.render('scripts/chief-portfolio', '/fixture/chief'), 'chief-portfolio', 'exec'), p.__dict__)
BODY = ('# Project status — Fixture\n\n**Landed:** Usable.\n\n**Next:** Lead will finish the export.\n\n'
        '**Your part:** Try it.\n\n**Updated:** 2026-10-19T12:00:00Z\n')


class PortfolioNotes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        self.store = self.root / 'knowledge'
        key = base64.urlsafe_b64encode(str(self.project).encode()).decode().rstrip('=')
        self.context = self.store / ('path_' + key) / 'context.json'
        self.context.parent.mkdir(parents=True)
        self.override = patch.object(p, 'KNOWLEDGE', self.store)
        self.override.start()
        self.addCleanup(self.override.stop)

    def save(self, notes):
        self.context.write_text(json.dumps({'version': 2, 'notes': notes}))

    def test_native_and_age(self):
        self.save([{'id': 'one', 'body': BODY, 'updatedAt': 1000000},
                   {'body': '# Unrelated\nLeave alone'}])
        (fields, date), reason = p.native_status(self.project)
        self.assertIsNone(reason)
        self.assertEqual(fields['Your part'], 'Try it.')
        self.assertEqual(date, 1000)
        self.assertIn('STALE!', p.note_age(date, date + 48 * 3600))
        self.assertNotIn('STALE!', p.note_age(date, date + 100))

    def test_body_date_and_unknown(self):
        self.save([{'body': BODY, 'updatedAt': 'bad'}])
        self.assertEqual(p.native_status(self.project)[0][1], p.stamp('2026-10-19T12:00:00Z'))
        self.save([{'body': BODY.replace('2026-10-19T12:00:00Z', 'bad')}])
        self.assertIn('UNKNOWN', p.note_age(p.native_status(self.project)[0][1], 1000))
        self.assertIn('UNKNOWN', p.note_age(2000, 1000))

    def test_missing_ambiguous_malformed(self):
        self.assertIsNone(p.native_status(self.project)[0])
        for notes in ([], [{'body': BODY}, {'body': BODY}],
                      [{'body': BODY.replace('**Next:**', 'Missing:')}],
                      [{'body': '# Desk status — old\n' + BODY}]):
            self.save(notes)
            self.assertIsNone(p.native_status(self.project)[0])
        self.context.write_text('{bad')
        self.assertIsNone(p.native_status(self.project)[0])
        self.context.write_text('[]')
        self.assertIsNone(p.native_status(self.project)[0])

    def test_compact_full_and_log_fallback(self):
        (self.root / 'brief.md').write_text(str(self.project / 'LEAD.md'))
        (self.project / 'LEAD.md').write_text('# Fixture\n## Status\nLog status\n## Waiting on the principal\n- Log ask\n')
        for full in (False, True):
            self.save([{'body': BODY}])
            with patch.object(p, 'HOME', self.root), patch.object(p, 'statuses', return_value={}), \
                    patch('sys.argv', ['chief-portfolio'] + (['--full'] if full else [])):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    p.main()
                for label in ('Landed: Usable.', 'Next: Lead will finish the export.', 'Your part: Try it.', 'Note updated'):
                    self.assertIn(label, out.getvalue())
                self.save([])
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    p.main()
                for text in ('LEAD fallback', 'log updated', 'Agent-owned', 'no action inferred'):
                    self.assertIn(text, out.getvalue())
                self.assertNotIn('Log ask', out.getvalue())

    def test_plain_output_and_explicit_private_detail(self):
        (self.root / 'brief.md').write_text(str(self.project / 'LEAD.md'))
        (self.project / 'LEAD.md').write_text('# Fixture\n## Status\nQ166 internal status\n')
        (self.root / 'open.md').write_text('## Waiting on the principal\n- Q166 choose\n'
                                          '## Promised by the chief\n- P47 delivery\n')
        (self.root / 'chief.json').write_text('{"session": "ses_private"}')
        self.save([{'body': BODY.replace('Lead will finish the export.', 'Verify.')
                   .replace('Try it.', 'Q166 / P47')}])
        for flags in ([], ['--full'], ['--private', '--full']):
            with patch.object(p, 'HOME', self.root), patch.object(p, 'statuses', return_value={}), \
                    patch('sys.argv', ['chief-portfolio'] + flags), contextlib.redirect_stdout(io.StringIO()) as out:
                p.main()
            text = out.getvalue()
            if '--private' in flags:
                self.assertIn('Q166 / P47', text)
                self.assertIn('ses_private', text)
            else:
                for token in ('Q166', 'P47', 'ses_private', 'Next: Verify.'):
                    self.assertNotIn(token, text)
                self.assertIn('no principal action inferred', text)
                self.assertIn('Suggested next action', text)
        self.assertEqual(p.human_field('Nothing needed from you; lead will finish the export.', 'Your part'),
                         'Nothing needed from you; lead will finish the export.')
        self.assertEqual(p.human_field('Q166: Keep the desktop HOLD; no remote commands.', 'Your part'),
                         'Keep the desktop HOLD; no remote commands.')

    def test_all_hosts_note_primary_and_retired_options(self):
        for host in ('opencode-lead.md', 'claude-lead-agent.md', 'codex-lead.config.toml'):
            template = 'hosts/' + host
            from effective_roles import effective
            text = effective(template, '/fixture/chief', ['checkpoint'])
            self.assertIn('Landed / Next / Your part / Updated Note', text)
            self.assertIn('reuse its ID', text)
            self.assertIn('never seed or auto-resync Knowledge', text)
            self.assertNotIn('one plan titled', text)
            self.assertNotIn('/desk/routes.json', text)
            with self.assertRaisesRegex(ValueError, 'retired'):
                r.render(template, '/fixture/chief', desk_project='old')
        with self.assertRaisesRegex(ValueError, 'retired'):
            r.desk_lead_values({}, '/fixture/chief', 'old')
        with self.assertRaisesRegex(ValueError, 'retired'):
            r.desk_checkpoint('historical workflow', '/fixture/chief', 'old')

    def inbox_output(self, private=True):
        out = io.StringIO()
        with patch.object(p, 'HOME', self.root), contextlib.redirect_stdout(out):
            p.inbox_summary(private)
        return out.getvalue()

    def test_inbox_zero_two_previews_and_no_mutation(self):
        self.assertEqual(self.inbox_output(), 'Chief inbox: 0 unread\n')
        inbox = self.root / 'inbox'
        inbox.mkdir()
        self.assertEqual(self.inbox_output(), 'Chief inbox: 0 unread\n')
        contents = {'a-project.md': '# Project A — landed\nDate: today\nResult usable.\n',
                    'b-project.md': '# Project B\n' + 'Long result ' * 100}
        for name, text in contents.items():
            (inbox / name).write_text(text)
        (inbox / 'nested').mkdir()
        (inbox / 'nested/ignored.md').write_text('nested')
        (self.root / 'archive/inbox').mkdir(parents=True)
        (self.root / 'archive/inbox/old.md').write_text('archived')
        (inbox / 'link.md').symlink_to(self.root / 'archive/inbox/old.md')
        out = self.inbox_output()
        self.assertIn('Chief inbox: 2 unread', out)
        self.assertEqual(len(out.splitlines()), 3)
        self.assertIn('a-project.md: Project A — landed Date: today Result usable.', out)
        self.assertIn('b-project.md: Project B Long result', out)
        self.assertTrue(all(len(line) <= p.WIDTH for line in out.splitlines()))
        self.assertNotIn('archived', out)
        self.assertNotIn('nested', out)
        public = self.inbox_output(private=False)
        self.assertIn('Agent-owned: chief to read and triage', public)
        self.assertNotIn('a-project.md', public)
        for name, text in contents.items():
            self.assertEqual((inbox / name).read_text(), text)

    def test_inbox_unreadable_is_counted(self):
        (self.root / 'inbox').mkdir()
        (self.root / 'inbox/bad.md').write_bytes(b'\xff')
        out = self.inbox_output()
        self.assertIn('1 unread', out)
        self.assertIn('bad.md: (unreadable entry)', out)
        with patch.object(p, 'read_small', side_effect=ValueError('file too large')):
            self.assertIn('(unreadable entry)', self.inbox_output())


if __name__ == '__main__':
    unittest.main()
