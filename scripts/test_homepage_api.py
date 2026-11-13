#!/usr/bin/env python3
"""Storage identity, unavailable sources and detail-query boundaries."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'builders/ansible/roles/observability-stack/files'))
from homepage_metrics import storage_pools
from homepage_api import HomepageData


def sample(instance, identity, value, **labels):
    return {'metric': {'instance': instance, 'id': identity, **labels}, 'value': [1, str(value)]}


class StoragePoolsTest(unittest.TestCase):
    def query(self, query):
        if 'pve_storage_info' in query:
            return [sample('a', 'storage/node-a/local', 1, node='node-a', storage='local', plugintype='dir'),
                    sample('b', 'storage/node-b/local', 1, node='node-b', storage='local', plugintype='lvmthin'),
                    sample('a', 'storage/node-a/backup', 1, node='node-a', storage='backup', plugintype='pbs')]
        if query.startswith('pve_disk_size_bytes'):
            return [sample('a','storage/node-a/local',100),sample('b','storage/node-b/local',900),sample('a','storage/node-a/backup',5000)]
        if query.startswith('pve_disk_usage_bytes'):
            return [sample('b','storage/node-b/local',300),sample('a','storage/node-a/local',40),sample('a','storage/node-a/backup',1000)]
        if query.startswith('pve_up'):
            return [sample('a','storage/node-a/local',1),sample('b','storage/node-b/local',1),sample('a','storage/node-a/backup',0)]
        if query.startswith('pve_storage_shared'):
            return [sample('a','storage/node-a/backup',1)]
        return [sample('a','',1),sample('b','',1)]

    def test_same_pool_name_on_two_nodes_does_not_mix_capacity(self):
        pools = storage_pools(self.query)
        a = next(p for p in pools if p['node']=='node-a' and p['name']=='local')
        b = next(p for p in pools if p['node']=='node-b')
        self.assertEqual((a['used'],a['total'],a['free']),(40,100,60))
        self.assertEqual((b['used'],b['total'],b['free']),(300,900,600))

    def test_unavailable_shared_pool_does_not_reuse_old_capacity(self):
        p = next(p for p in storage_pools(self.query) if p['name']=='backup')
        self.assertFalse(p['active'])
        self.assertTrue(p['shared'])
        self.assertIsNone(p['used']);self.assertIsNone(p['total']);self.assertIsNone(p['free'])

    def test_failed_exporter_scrape_invalidates_available_pool(self):
        def query(q):
            return [] if q.startswith('up{') else self.query(q)
        self.assertTrue(all(p['total'] is None for p in storage_pools(query)))


class DetailBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.data=HomepageData('/unused','http://prom','http://loki')
        self.snapshot={'operations':{'nodes':[{'name':'pve','guests':[{'name':'mine','tags':'autolab'},{'name':'tenant','tags':'autolab;tenant-qnta'}]}],
          'telemetry':{'containers':[{'host':'mine','name':'app'},{'host':'tenant','name':'private-app'}]}}}
        self.data.snapshot=lambda:self.snapshot

    def test_host_vm_container_and_range_must_exist(self):
        for args in [('unknown',),('pve','unknown'),('pve','mine','unknown'),('pve','mine','app','100d'),('pve','tenant','private-app')]:
            with self.subTest(args=args),self.assertRaises(ValueError):self.data.detail(*args)

    def test_container_logs_are_scoped_and_loki_values_are_plain_text(self):
        urls=[]
        def get(url):
            urls.append(url)
            if 'query_range' in url and url.startswith('http://loki'):
                return {'data':{'result':[{'stream':{'container':'app'},'values':[['1000000000','<script>untrusted log</script>']]}]}}
            return {'data':{'result':[]}}
        with patch('homepage_api.get_json',side_effect=get):result=self.data.detail('pve','mine','app')
        from urllib.parse import parse_qs,urlsplit
        log_query=parse_qs(urlsplit(next(u for u in urls if u.startswith('http://loki'))).query)['query'][0]
        self.assertEqual(log_query,'{host="mine",job="docker",container="app"}')
        self.assertEqual(result['logs'][0]['text'],'<script>untrusted log</script>')

    def test_tenant_view_omits_application_containers_and_queries_only_journal(self):
        urls=[]
        def get(url):urls.append(url);return {'data':{'result':[]}}
        with patch('homepage_api.get_json',side_effect=get):result=self.data.detail('pve','tenant')
        self.assertEqual(result['containers'],[])
        self.assertTrue(result['tenant'])
        self.assertTrue(any('journald' in url for url in urls if url.startswith('http://loki')))


if __name__=='__main__':unittest.main()
