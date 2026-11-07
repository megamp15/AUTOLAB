#!/usr/bin/env python3
"""Exercise the collector functions without contacting a real lab."""
import ast
import datetime as dt
import json
import subprocess
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'builders/ansible/roles/observability-stack/templates/autolab-obs-digest.py.j2'
TREE = ast.parse(SOURCE.read_text())
FUNCTIONS = ast.Module(body=[n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name in ('operations', 'link_access')], type_ignores=[])


class HomepageOperationsTest(unittest.TestCase):
    def setUp(self):
        self.scope = {'dt': dt, 'json': json, 'subprocess': subprocess, 'urllib': urllib, 'os': __import__('os'),
                      'NODES': [{'name': 'healthy'}, {'name': 'offline'}], 'PBS_URL': ''}
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
