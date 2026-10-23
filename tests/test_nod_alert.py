"""nod-alert posts the documented Nod request shape; a local mock server stands in for Nod."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC / 'scripts'))
import render  # noqa: E402

SEEN = []


class Handler(BaseHTTPRequestHandler):
    status = 200

    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        SEEN.append((self.path, self.headers.get('Authorization'), json.loads(body)))
        self.send_response(self.status)
        self.end_headers()
        self.wfile.write(json.dumps({'request_id': 'req_1', 'deduped': False} if self.status == 200
                                    else {'error': 'bad token'}).encode())

    def log_message(self, *a):
        pass


class NodAlertTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.script = Path(self.tmp.name) / 'nod-alert'
        self.script.write_text(render.render('scripts/nod-alert', '/fixture/chief'))
        Handler.status = 200
        SEEN.clear()
        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.env = {'PATH': os.environ['PATH'], 'NOD_BASE_URL': f'http://127.0.0.1:{self.server.server_port}'}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def run_cli(self, *args, **env):
        return subprocess.run([sys.executable, '-I', str(self.script), *args], env={**self.env, **env},
                              capture_output=True, text=True, timeout=30)

    def test_posts_default_channel_with_bearer_token_from_file(self):
        token = Path(self.tmp.name) / 'issuer.token'
        token.write_text('secret-token\n')
        out = self.run_cli('Heat lost weather', '--summary', 'no data', '--dedupe-key', 'k1',
                           NOD_ISSUER_TOKEN_FILE=str(token))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('req_1', out.stdout)
        self.assertNotIn('secret-token', out.stdout + out.stderr)
        path, auth, body = SEEN[0]
        self.assertEqual((path, auth), ('/api/v1/requests', 'Bearer secret-token'))
        self.assertEqual(body, {'title': 'Heat lost weather', 'channel_id': 'default',
                                'summary': 'no data', 'dedupe_key': 'k1'})

    def test_server_error_is_reported_without_the_token(self):
        Handler.status = 401
        out = self.run_cli('x', NOD_ISSUER_TOKEN='secret-token')
        self.assertEqual(out.returncode, 1)
        self.assertIn('HTTP 401', out.stderr)
        self.assertNotIn('bad token', out.stderr)  # response body is never echoed
        self.assertNotIn('secret-token', out.stderr)

    def test_missing_token_and_dry_run(self):
        out = self.run_cli('x')
        self.assertEqual(out.returncode, 1)
        self.assertIn('NOD_ISSUER_TOKEN', out.stderr)
        self.assertEqual(SEEN, [])
        dry = self.run_cli('x', '--dry-run')
        self.assertEqual(dry.returncode, 0)
        self.assertIn('"channel_id": "default"', dry.stdout)
        self.assertEqual(SEEN, [])

    def test_opencode_lead_may_read_exactly_the_home_infra_reference(self):
        lead = render.render('hosts/opencode-lead.md', '/fixture/chief')
        ref = str(Path.home() / '.local/share/chief-of-staff/home-infra.md')
        from access_policy import agent_parts, winner
        rules = agent_parts(lead)[2]
        for action in ('external_directory', 'read'):
            self.assertEqual(winner(action, ref, rules)['effect'], 'allow')
            self.assertNotEqual(winner(action, str(Path(ref).with_name('private.md')), rules)['effect'], 'allow')
        self.assertEqual(winner('edit', ref, rules)['effect'], 'deny')


if __name__ == '__main__':
    unittest.main()
