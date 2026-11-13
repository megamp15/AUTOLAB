#!/usr/bin/env python3
"""Exercise the collector functions without contacting a real lab."""
import ast
import sys
import datetime as dt
import json
import subprocess
import ssl
import urllib.request
import urllib.error
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch, mock_open


SOURCE = Path(__file__).resolve().parents[1] / 'builders/ansible/roles/observability-stack/templates/autolab-obs-digest.py.j2'
sys.path.insert(0, str(SOURCE.parents[1] / 'files'))
TREE = ast.parse(SOURCE.read_text())
FUNCTIONS = ast.Module(body=[n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name in ('operations', 'link_access', 'probe', 'write_metrics', 'complete_snapshots', 'telemetry')], type_ignores=[])


class HomepageOperationsTest(unittest.TestCase):
    def setUp(self):
        self.scope = {'dt': dt, 'json': json, 'subprocess': subprocess, 'urllib': urllib, 'os': __import__('os'),
                      'NODES': [{'name': 'healthy'}, {'name': 'offline'}], 'PBS_URL': '', 'ssl': ssl}
        exec(compile(FUNCTIONS, str(SOURCE), 'exec'), self.scope)

    def test_one_unreachable_node_does_not_erase_other_jobs_or_guests(self):
        def pve(node, path):
            if node['name'] == 'offline':
                raise OSError('unavailable')
            if path.startswith('/cluster/resources'):
                return [{'name': 'probe', 'vmid': 100, 'status': 'running'}]
            if path.endswith('/time'):
                return {'timezone': 'America/Chicago'}
            return [{'schedule': '02:00', 'next-run': 12345, 'storage': 'ark'}]
        self.scope['pve'] = pve
        with patch.object(subprocess, 'check_output', return_value='[]'):
            result = self.scope['operations']({})
        self.assertEqual(result['schedules'][0]['next'], 12345)
        self.assertEqual(result['schedules'][0]['timezone'], 'America/Chicago')
        self.assertEqual(result['nodes'][0]['guests'][0]['name'], 'probe')
        self.assertFalse(result['nodes'][1]['available'])
        self.assertIn('offline: OSError', result['errors'])
        self.assertNotIn('secret', json.dumps(result))

    def test_telemetry_groups_hosts_and_containers_and_a_failure_stays_local(self):
        def prom(query):
            if 'node_cpu_seconds_total{mode="idle"})' in query and query.startswith('count'):
                return [{'metric': {'instance': 'jwst'}, 'value': [0, '4']}]
            if 'container_memory_working_set_bytes' in query:
                return [{'metric': {'instance': 'jwst', 'name': 'services-code-server-1'}, 'value': [0, '1048576']},
                        {'metric': {'instance': 'jwst'}, 'value': [0, '1']}]
            return []
        self.scope['prom'] = prom
        result = self.scope['telemetry']()
        self.assertEqual(result['hosts'], [{'name': 'jwst', 'cores': 4.0}])
        self.assertEqual(result['containers'], [{'host': 'jwst', 'name': 'services-code-server-1', 'mem': 1048576.0}])

        def broken(query):
            raise OSError('prometheus down')
        self.scope['prom'] = broken
        self.scope['pve'] = lambda node, path: [] if 'resources' in path or 'backup' in path else {}
        with patch.object(subprocess, 'check_output', return_value='[]'):
            result = self.scope['operations']({})
        self.assertIn('telemetry: OSError', result['errors'])
        self.assertEqual(len(result['nodes']), 2)

    def test_in_progress_snapshot_does_not_clear_missing_backup_metrics(self):
        self.scope.update({
            'guests_everywhere': lambda: [({}, {'name':'probe', 'vmid':100})],
            'excluded_everywhere': lambda: set(),
            'PBS_DATASTORES': ['store'], 'BACKUP_STORAGE':'store',
            'NOW': dt.datetime.fromtimestamp(200000, dt.timezone.utc),
            'pbs': lambda path: [
                {'backup-id':'100', 'backup-time':100000, 'size':4096},
                {'backup-id':'100', 'backup-time':199999, 'size':None},
            ],
        })
        writer = mock_open()
        with patch('builtins.open', writer), patch.object(self.scope['os'], 'makedirs'), patch.object(self.scope['os'], 'replace'):
            self.scope['write_metrics']()
        output = ''.join(call.args[0] for call in writer().write.call_args_list)
        self.assertIn('autolab_backup_last_seconds{name="probe",vmid="100"} 100000', output)
        self.assertNotIn('199999', output)

    def test_auth_proxy_response_does_not_hide_an_unhealthy_backend(self):
        check = {'type': 'docker', 'target': 'services-dockhand-1', 'url': 'http://jwst:9000/'}
        with patch.object(subprocess, 'check_output', return_value='[{"State":{"Health":{"Status":"unhealthy"}}}]'):
            self.assertFalse(self.scope['probe'](check))

    def test_access_labels_distinguish_public_internal_and_direct_endpoints(self):
        conf = {'public_zone': 'example.com', 'internal_label': 'lab'}
        label = self.scope['link_access']
        self.assertEqual(label('https://home.example.com', conf), 'Public + Pocket ID')
        self.assertEqual(label('https://dockhand.lab.example.com', conf), 'Tailscale + Pocket ID')
        self.assertEqual(label('https://immich.lab.example.com', conf), 'Tailscale · app login')
        self.assertEqual(label('http://jwst.example.ts.net:9090', conf), 'Tailscale · direct')
        self.assertEqual(label('https://share.example.com/share/key', conf), 'Public · shared links')
        self.assertEqual(label('https://github.com/megamp15/AUTOLAB', conf), 'External · account')


if __name__ == '__main__':
    unittest.main()
