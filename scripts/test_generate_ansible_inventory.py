#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("generate-ansible-inventory.py")


class GenerateInventoryTest(unittest.TestCase):
    def run_script(self, value):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "machines.json"
            source.write_text(json.dumps(value))
            return subprocess.run(
                [sys.executable, str(SCRIPT), str(source)],
                capture_output=True,
                text=True,
            )

    def test_backup_server_flag_passes_through(self):
        value = {"one": {
            "name": "ark", "ansible_host": "10.42.0.11", "bootstrap_user": "root",
            "builder": {"enabled": True, "backup": {"server": True}},
        }}
        result = self.run_script(value)
        self.assertEqual(result.returncode, 0)
        host = json.loads(result.stdout)["all"]["children"]["linux_servers"]["hosts"]["ark"]
        self.assertTrue(host["autolab_builder"]["backup"]["server"])

    def test_backup_server_must_be_boolean(self):
        value = {"one": {
            "name": "ark", "ansible_host": "10.42.0.11", "bootstrap_user": "root",
            "builder": {"enabled": True, "backup": {"server": "yes"}},
        }}
        result = self.run_script(value)
        self.assertEqual(result.returncode, 1)
        self.assertIn("builder.backup.server must be a boolean", result.stderr)

    def test_valid_input(self):
        value = {"one": {
            "name": "lab-01", "ansible_host": "10.0.0.1", "bootstrap_user": "root",
            "builder": {"enabled": True, "docker_enabled": False,
                         "firewall_rules": [{"port": 22, "protocol": "tcp", "source": "10.0.0.0/8"}]},
        }}
        result = self.run_script(value)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["all"]["children"]["linux_servers"]["hosts"]["lab-01"]["ansible_host"], "10.0.0.1")
        self.assertNotIn("tailscale_ssh_enabled", json.loads(result.stdout)["all"]["children"]["linux_servers"]["hosts"]["lab-01"]["autolab_builder"])
        self.assertEqual(result.stderr, "")

    def test_tailscale_ssh_policy_is_not_required(self):
        value = {"one": {
            "name": "lab-01", "ansible_host": "100.64.0.1", "bootstrap_user": "root",
            "builder": {"enabled": True, "docker_enabled": True},
        }}
        result = self.run_script(value)
        self.assertEqual(result.returncode, 0)
        builder = json.loads(result.stdout)["all"]["children"]["linux_servers"]["hosts"]["lab-01"]["autolab_builder"]
        self.assertEqual(builder, {"enabled": True, "docker_enabled": True})

    def test_tenant_host_hops_through_the_hypervisor(self):
        value = {"one": {
            "name": "qnta-mgmt", "ansible_host": "10.42.0.201", "bootstrap_user": "autolab",
            "ssh_jump_host": "xps-pve.example.ts.net",
            "builder": {"enabled": True},
        }}
        result = self.run_script(value)
        self.assertEqual(result.returncode, 0)
        host = json.loads(result.stdout)["all"]["children"]["linux_servers"]["hosts"]["qnta-mgmt"]
        self.assertEqual(host["ansible_host"], "10.42.0.201")
        self.assertEqual(host["autolab_ssh_jump_host"], "xps-pve.example.ts.net")
        self.assertEqual(host["ansible_ssh_common_args"], "-o StrictHostKeyChecking=yes -o ProxyJump=gitops@xps-pve.example.ts.net")

    def test_provider_host_has_no_jump(self):
        value = {"one": {
            "name": "lab-01", "ansible_host": "lab-01", "bootstrap_user": "root",
            "ssh_jump_host": None,
            "builder": {"enabled": True},
        }}
        result = self.run_script(value)
        self.assertEqual(result.returncode, 0)
        host = json.loads(result.stdout)["all"]["children"]["linux_servers"]["hosts"]["lab-01"]
        self.assertNotIn("ansible_ssh_common_args", host)
        self.assertNotIn("autolab_ssh_jump_host", host)

    def test_empty_jump_is_rejected(self):
        value = {"one": {"name": "lab-01", "ansible_host": "10.0.0.1", "bootstrap_user": "root", "ssh_jump_host": "", "builder": {"enabled": True}}}
        result = self.run_script(value)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ssh_jump_host", result.stderr)

    def test_storage_entries_pass_through(self):
        value = {"one": {
            "name": "qnta-mgmt", "ansible_host": "10.42.0.201", "bootstrap_user": "autolab",
            "builder": {"enabled": True, "storage": [
                {"protocol": "smb", "server": "192.168.50.163", "share": "qnta", "path": "/mnt/qnta", "credential": "nas", "directories": ["qnta-mgmt"]},
            ]},
        }}
        result = self.run_script(value)
        self.assertEqual(result.returncode, 0)
        storage = json.loads(result.stdout)["all"]["children"]["linux_servers"]["hosts"]["qnta-mgmt"]["autolab_builder"]["storage"]
        self.assertEqual(storage[0]["share"], "qnta")

    def test_smb_storage_needs_a_credential(self):
        value = {"one": {
            "name": "qnta-mgmt", "ansible_host": "10.42.0.201", "bootstrap_user": "autolab",
            "builder": {"enabled": True, "storage": [
                {"protocol": "smb", "server": "192.168.50.163", "share": "qnta", "path": "/mnt/qnta", "credential": None},
            ]},
        }}
        result = self.run_script(value)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("credential", result.stderr)

    def test_storage_without_a_server_is_rejected(self):
        # tofu fills server from nas_server; if that was unset the entry
        # reaches here with null, and the playbook would mount from nowhere.
        value = {"one": {
            "name": "qnta-mgmt", "ansible_host": "10.42.0.201", "bootstrap_user": "autolab",
            "builder": {"enabled": True, "storage": [
                {"protocol": "nfs", "server": None, "share": "/volume1/autolab", "path": "/mnt/autolab"},
            ]},
        }}
        result = self.run_script(value)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("server", result.stderr)

    def test_malformed_contract(self):
        result = self.run_script({"one": {"name": "lab-01", "ansible_host": "10.0.0.1", "bootstrap_user": "root", "builder": {"enabled": "yes"}}})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("builder.enabled", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_empty_enabled_set(self):
        value = {"one": {"name": "lab-01", "ansible_host": "10.0.0.1", "bootstrap_user": "root", "builder": {"enabled": False}}}
        result = self.run_script(value)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no enabled builder hosts", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
