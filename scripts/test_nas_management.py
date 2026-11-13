"""Guard private management access and the Portainer retirement sequence."""

from pathlib import Path
import unittest

import jinja2
import yaml


ROLE = Path(__file__).resolve().parents[1] / "builders/ansible/roles/nas-management"


class NasManagementTest(unittest.TestCase):
    def render(self):
        values = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
        values.update(inventory_hostname="singularity", autolab_nas_management_ip="100.64.0.10")
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        template = env.from_string((ROLE / "templates/docker-compose.yml.j2").read_text())
        return yaml.safe_load(template.render(**values))

    def test_agent_is_authenticated_and_binds_only_the_tailnet_address(self):
        agent = self.render()["services"]["hawser"]
        self.assertEqual(agent["ports"], ["100.64.0.10:2376:2376"])
        self.assertEqual(agent["environment"]["TOKEN_FILE"], "/run/secrets/hawser-token")
        self.assertNotIn("TOKEN", agent["environment"])
        self.assertEqual(agent["environment"]["STACKS_DIR"], "/volume1/docker")

    def test_desktop_launcher_has_no_docker_control(self):
        services = self.render()["services"]
        self.assertEqual(set(services), {"hawser", "dockhand-launcher"})
        launcher = services["dockhand-launcher"]
        self.assertTrue(all("docker.sock" not in volume for volume in launcher["volumes"]))
        self.assertEqual(launcher["ports"], ["100.64.0.10:9000:80", "127.0.0.1:9000:80"])

    def test_portainer_removal_waits_for_connection_verification_and_preserves_data(self):
        tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
        register_index = next(i for i, task in enumerate(tasks) if task.get("ansible.builtin.include_tasks") == "register.yml")
        remove_index = next(i for i, task in enumerate(tasks) if "community.docker.docker_container" in task)
        self.assertLess(register_index, remove_index)
        removal = tasks[remove_index]
        self.assertEqual(removal["community.docker.docker_container"]["name"], "Portainer")
        self.assertTrue(removal["community.docker.docker_container"]["keep_volumes"])
        self.assertIn("autolab_nas_dockhand_test.json.success", removal["when"])
        self.assertTrue(any("autolab_nas_protected_before.stdout == autolab_nas_protected_after.stdout" in str(task) for task in tasks))


if __name__ == "__main__":
    unittest.main()
