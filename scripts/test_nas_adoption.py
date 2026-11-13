"""Protect adoption boundaries and the recovered photo sorter's existing behavior."""

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
        compose = yaml.safe_load((ROLE / "files/photo-sort/docker-compose.yaml").read_text())
        self.assertEqual(compose["services"]["sort"]["environment"]["MODE"], "${MODE:-plan}")


class RecoveredSorterTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.media = Path(self.temp.name) / "media"
        self.job = Path(self.temp.name) / "job"
        self.media.mkdir(); self.job.mkdir()
        with patch.dict(os.environ, ROOT=str(self.media), JOB=str(self.job), MODE="plan", DUPLICATES="move"):
            spec = importlib.util.spec_from_file_location("recovered_sorter", ROLE / "files/photo-sort/sort.py")
            self.sorter = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.sorter)

    def test_nested_loose_folder_is_flattened_into_recording_month(self):
        source = self.media / "_inbox/loose/uploaded-folder/photo.jpg"
        source.parent.mkdir(parents=True); source.write_bytes(b"example photo")
        with patch.object(self.sorter, "recording_months", return_value={str(source): "2026-09"}):
            self.sorter.Sorter(True).run()
        self.assertTrue((self.media / "library/2026/09/photo.jpg").is_file())
        self.assertFalse((self.media / "library/2026/09/uploaded-folder").exists())

    def test_named_event_stays_grouped_and_uses_recording_dates(self):
        folder = self.media / "_inbox/events/Trip"
        folder.mkdir(parents=True)
        first = folder / "a.jpg"; first.write_bytes(b"photo a")
        second = folder / "b.jpg"; second.write_bytes(b"photo b")
        with patch.object(self.sorter, "recording_months", return_value={str(first): "2026-09", str(second): "2026-09"}):
            self.sorter.Sorter(True).run()
        self.assertTrue((self.media / "library/2026/09/Trip/a.jpg").is_file())
        self.assertTrue((self.media / "library/2026/09/Trip/b.jpg").is_file())


if __name__ == "__main__":
    unittest.main()
