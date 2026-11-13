"""Render appliance telemetry and guard host identity and project isolation."""

import argparse
from pathlib import Path
import sys
import unittest

import jinja2
import yaml


ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "builders/ansible/roles/nas-observability"


def render():
    values = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
    values["inventory_hostname"] = "singularity"
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    # Resolve endpoint expressions from the role defaults before the templates.
    for key, value in list(values.items()):
        if isinstance(value, str):
            values[key] = env.from_string(value).render(**values)
    return {name: env.from_string((ROLE / "templates" / (name + ".j2")).read_text()).render(**values)
            for name in ("docker-compose.yml", "config.alloy")}


class NasObservabilityTest(unittest.TestCase):
    def test_collects_host_filesystems_and_uses_stable_nas_identity(self):
        rendered = render()
        config = rendered["config.alloy"]
        compose = yaml.safe_load(rendered["docker-compose.yml"])
        self.assertIn('rootfs_path    = "/host/root"', config)
        self.assertIn('replacement  = "singularity"', config)
        self.assertIn('"instance" = "singularity"', config)
        self.assertIn("/:/host/root:ro,rslave", compose["services"]["alloy"]["volumes"])
        self.assertIn('job"', config)

    def test_no_public_exporter_ports_or_application_services(self):
        compose = yaml.safe_load(render()["docker-compose.yml"])
        self.assertEqual(set(compose["services"]), {"alloy", "cadvisor"})
        self.assertNotIn("ports", compose["services"]["alloy"])
        self.assertTrue(all(port.startswith("127.0.0.1:") for port in compose["services"]["cadvisor"]["ports"]))
        self.assertIn("127.0.0.1:12345", " ".join(compose["services"]["alloy"]["command"]))

    def test_nas_is_excluded_from_vm_inventory_and_has_no_os_roles(self):
        inventory = yaml.safe_load((ROOT / "builders/ansible/inventories/nas/hosts.yml").read_text())
        self.assertNotIn("linux_servers", inventory["all"]["children"])
        play = yaml.safe_load((ROOT / "builders/ansible/playbooks/nas.yml").read_text())[0]
        self.assertEqual([role["role"] for role in play["roles"]], ["nas-projects", "nas-observability", "nas-management"])
        self.assertEqual(play["vars"]["autolab_nas_action"], "inspect")
        tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
        deploy = next(task["community.docker.docker_compose_v2"] for task in tasks if "community.docker.docker_compose_v2" in task)
        self.assertFalse(deploy["remove_orphans"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--render", type=Path)
    args, rest = parser.parse_known_args()
    if args.render:
        args.render.mkdir(parents=True, exist_ok=True)
        for name, text in render().items():
            (args.render / name).write_text(text)
    else:
        unittest.main(argv=[sys.argv[0], *rest])
