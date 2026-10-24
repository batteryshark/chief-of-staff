"""Docket decided v1 normal CLI boundary. No guest/native/agent auth fallback."""
import json
import os
import selectors
import subprocess
import time
from datetime import datetime, timedelta, timezone

import tower_schema as schema


def call(executable, argv):
    env = {k:os.environ[k] for k in ('HOME','PATH','LANG','LC_ALL') if k in os.environ}
    process = subprocess.Popen([executable,*argv],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL,env=env)
    output = bytearray(); deadline = time.monotonic()+8
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout,selectors.EVENT_READ)
            while True:
                remaining = deadline-time.monotonic()
                if remaining <= 0 or not selector.select(remaining): raise ValueError('Docket timeout')
                raw = os.read(process.stdout.fileno(),min(8192,65537-len(output)))
                if not raw: break
                output.extend(raw)
                if len(output)>65536: raise ValueError('Docket output bound')
        code = process.wait(timeout=max(.01,deadline-time.monotonic()))
        if code: raise ValueError('Docket unavailable; owner must inspect normal client')
        return json.loads(output)
    finally:
        if process.poll() is None: process.kill(); process.wait()
        process.stdout.close()


class Docket:
    def __init__(self, executable, request=call):
        self.executable,self.request = executable,request

    def invoke(self, *argv):
        value = self.request(self.executable,list(argv)); schema.depth(value)
        return value

    def markers(self):
        value = self.invoke('project-markers','--json')
        schema.obj(value,'version source observed_at complete markers')
        if type(value.get('version')) is not int or value['version']!=1 or value.get('source')!='docket.project-markers' or value.get('complete') is not True:
            raise ValueError('Docket marker read unknown')
        schema.stamp(value.get('observed_at')); result=[]; seen=set()
        from tower_refresh import marker
        for m in schema.seq(value.get('markers'),20):
            schema.obj(m,'id session directory milestone_at milestone_ref roster_state')
            if m.get('id') in seen: raise ValueError('duplicate marker')
            seen.add(m.get('id'))
            result.append(marker(dict(id=m.get('id'),version=1,lead_session=m.get('session'),directory=m.get('directory'),
                milestone_at=m.get('milestone_at'),milestone_ref=m.get('milestone_ref'),roster_state=m.get('roster_state'),
                observed_at=value['observed_at'],provenance='recorded_marker_observation')))
        return result

    def lease(self, value):
        schema.obj(value,'version source observed_at changed schedule')
        if 'schedule' not in value or type(value.get('version')) is not int or value['version']!=1 or value.get('source')!='docket.tower-refresh-schedule' or type(value.get('changed')) is not bool:
            raise ValueError('Docket lease read unknown')
        schema.stamp(value.get('observed_at'))
        s=value.get('schedule')
        if s is None: return None
        schema.obj(s,'item_id status purpose every_seconds anchor next_fire_at until lease_expired cancelled_at last_occurrence')
        if s.get('item_id')!='dkt_tower_refresh' or s.get('purpose')!='project_pages' or type(s.get('every_seconds')) is not int or s['every_seconds']!=900 or type(s.get('lease_expired')) is not bool:
            raise ValueError('Docket lease binding')
        schema.text(s.get('status'),40); schema.stamp(s.get('anchor'))
        future_time(s.get('until'))
        if s.get('next_fire_at') is not None: future_time(s['next_fire_at'])
        if s.get('cancelled_at') is not None: schema.stamp(s['cancelled_at'])
        last=s.get('last_occurrence')
        if last is not None:
            schema.obj(last,'id status scheduled_at queue_result')
            schema.ident(last.get('id')); schema.text(last.get('status'),40); schema.stamp(last.get('scheduled_at'))
            if last.get('queue_result') not in (None,'accepted','full','disabled','uncertain'): raise ValueError('queue result')
        return s

    def reconcile(self, now=None):
        now=now or datetime.now(timezone.utc)
        current=self.lease(self.invoke('tower-refresh','show','--json'))
        if current:
            if current.get('cancelled_at') is not None or current['status']=='cancelled':
                return 'cancelled' # Never resurrect, including an old queued notice.
            if current['lease_expired'] or future_time(current['until']) <= now:
                raise ValueError('Snapshot lease expired; owner must explicitly renew')
            if current['status'] != 'pending': raise ValueError('Snapshot lease needs owner review')
            if future_time(current['until'])-now >= timedelta(days=7): return 'active'
        until=(now+timedelta(days=89)).isoformat()
        renewed=self.lease(self.invoke('tower-refresh','ensure','--until',until,'--json'))
        if not renewed or renewed['status']!='pending' or renewed['lease_expired'] or renewed.get('cancelled_at') is not None:
            raise ValueError('Docket renewal not confirmed')
        if not future_time(until) <= future_time(renewed['until']) <= now+timedelta(days=90):
            raise ValueError('Docket renewal deadline not confirmed')
        if current and renewed['anchor'] != current['anchor']: raise ValueError('Docket anchor changed')
        return 'renewed'


def future_time(value):
    schema.text(value,40)
    # Same strict timestamp syntax/year bounds; permit future lease deadlines only here.
    import re
    if not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)',value): raise ValueError('lease timestamp')
    t=datetime.fromisoformat(value.replace('Z','+00:00'))
    if not 2000<=t.year<=2100: raise ValueError('lease year')
    return t
