"""Protect the boundaries of adopting the NAS's existing projects."""

from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "builders/ansible/roles/nas-projects"


class NasAdoptionTest(unittest.TestCase):
    def test_immich_media_stays_read_only_and_uses_existing_state(self):
        compose = yaml.safe_load((ROLE / "files/immich/docker-compose.yaml").read_text())
        server = compose["services"]["immich-server"]
        self.assertIn("/home/Mahir/media:/mnt/mahir-personal:ro", server["volumes"])
        self.assertEqual(server["env_file"], [".env"])
        self.assertIn("${DB_DATA_LOCATION}:/var/lib/postgresql/data", compose["services"]["database"]["volumes"])

    def test_adoption_never_calls_compose_up_or_removes_projects(self):
        tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
        for task in tasks:
            self.assertNotIn("community.docker.docker_compose_v2", task)
            argv = task.get("ansible.builtin.command", {}).get("argv", [])
            for forbidden in ("up", "down", "pull", "build", "rm"):
                self.assertNotIn(forbidden, argv)


if __name__ == "__main__":
    unittest.main()
