"""Goal metadata over Docket's existing paired adapter; no host/credential discovery of our own."""
import json
import os
import re
import sys
from urllib.parse import urlencode

source = sys.argv[1]
if not os.path.isabs(source):
    raise SystemExit('Explicit Docket client required')
sys.path.insert(0, source)
from docket.host import configured_adapter
try:
    data = json.load(sys.stdin)
    sid, directory = data['sessionID'], data['directory']
    if not re.fullmatch(r'ses_[A-Za-z0-9]+', sid) or not os.path.isabs(directory):
        raise ValueError()
    patch = data.get('patch')
    if patch is not None:
        goal = patch['openchamber']['goal']
        if set(patch) != {'openchamber'} or set(patch['openchamber']) != {'goal'} or set(goal) != {'status', 'statusReason', 'updatedAt'} or goal['status'] not in ('active', 'paused'):
            raise ValueError()
    adapter = configured_adapter()
    path = '/api/openchamber/sessions/' + sid + '/metadata'
    status, result = adapter._request('POST' if patch else 'GET', path if patch else path + '?' + urlencode({'directory': directory}),
                                     {'directory': directory, 'patch': patch} if patch else None)
    if status != 200 or adapter.host_status().get('mode') != 'paired':
        raise ValueError()
    print(json.dumps(result['metadata']))
except Exception:
    raise SystemExit('Paired goal metadata unavailable; no fallback or host restart')
