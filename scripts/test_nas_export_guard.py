import importlib.util
from pathlib import Path
import socket
import unittest

path = Path(__file__).resolve().parents[1] / 'builders/ansible/roles/nas-observability/files/autolab-nfs-export-guard.py'
spec = importlib.util.spec_from_file_location('nas_export_guard', path)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class ExportGuardTest(unittest.TestCase):
    config = '/volume1/autolab ark.example.ts.net(rw,async,no_root_squash)\n/volume1/autolab nebula.example.ts.net(ro,sync,root_squash)\n'
    active = '/volume1/autolab ark.example.ts.net(rw,async,no_root_squash)\n'

    def test_only_missing_configured_rule_is_restored_with_its_options(self):
        calls = []
        count = guard.recover(self.config, self.active, lambda host: None, lambda host, opts: calls.append((host, opts)))
        self.assertEqual(count, 1)
        self.assertEqual(calls, [('nebula.example.ts.net', 'ro,sync,root_squash')])

    def test_all_missing_rules_are_recovered(self):
        calls = []
        self.assertEqual(guard.recover(self.config, "", lambda _: None, lambda *args: calls.append(args)), 2)
        self.assertEqual(len(calls), 2)

    def test_dns_failure_never_changes_any_rules(self):
        calls = []
        def fail(host):
            raise socket.gaierror('temporary failure')
        with self.assertRaises(socket.gaierror):
            guard.recover(self.config, self.active, fail, lambda *args: calls.append(args))
        self.assertEqual(calls, [])

    def test_unknown_rule_syntax_refuses_to_change_exports(self):
        with self.assertRaises(ValueError):
            guard.configured(self.config + '/volume1/autolab *(rw)\n')

    def test_no_reload_when_all_rules_active(self):
        self.assertEqual(guard.recover(self.config, self.config, lambda _: self.fail(), lambda *args: self.fail()), 0)
