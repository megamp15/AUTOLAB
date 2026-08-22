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
