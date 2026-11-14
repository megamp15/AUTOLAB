"""The services a machine runs, as the machines map and as the ingress sees them.

The ingress run and the homepage only have the lab Stack's inventory, so
services on machines in other Stacks are named once in group_vars
(autolab_remote_services). This is the check that the two lists cannot drift:
a service enabled on a machine and not named there would have no route; a name
there with no service behind it would route to a closed port.
"""
import re
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
GROUP_VARS = yaml.safe_load((ROOT / "builders/ansible/playbooks/group_vars/all.yml").read_text())


def machine_services(path):
    """name -> services list, for every machine block in a machines tfvars."""
    out = {}
    text = path.read_text()
    # A machine starts at `  <key> = {` at two-space indent and ends before the next one.
    blocks = re.split(r"^  (?=\w+ = \{$)", text, flags=re.MULTILINE)[1:]
    for block in blocks:
        name = re.match(r"(\w+) = \{", block).group(1)
        found = re.search(r"^\s+services\s*=\s*\[([^\]]*)\]", block, re.MULTILINE)
        out[name] = re.findall(r'"([^"]+)"', found.group(1)) if found else []
    return out


class RemoteServicesTest(unittest.TestCase):
    def test_lab_services_are_all_in_the_catalog(self):
        catalog = set(GROUP_VARS["autolab_service_catalog"])
        for stack in ("lab", "edge"):
            for machine, services in machine_services(ROOT / f"infra/stacks/{stack}/machines.auto.tfvars").items():
                with self.subTest(machine=machine):
                    self.assertLessEqual(set(services), catalog)

    def test_remote_services_match_the_edge_machines_map(self):
        edge = {m: s for m, s in machine_services(ROOT / "infra/stacks/edge/machines.auto.tfvars").items() if s}
        self.assertEqual(GROUP_VARS["autolab_remote_services"], edge)

    def test_a_service_runs_on_one_machine_only(self):
        seen = {}
        for stack in ("lab", "edge"):
            for machine, services in machine_services(ROOT / f"infra/stacks/{stack}/machines.auto.tfvars").items():
                for name in services:
                    self.assertNotIn(name, seen, f"{name} is on {machine} and {seen.get(name)}")
                    seen[name] = machine


if __name__ == "__main__":
    unittest.main()
