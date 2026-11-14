"""Exercise the provisioning script without exposing an API key."""
import contextlib
import io
import os
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'builders/ansible/roles/container-services/files/adventurelog/immich_integration.py'


class Integration:
    def __init__(self, server_url, api_key):
        self.server_url = server_url
        self.api_key = api_key

    def save(self, update_fields):
        self.saved = update_fields


class ProvisioningTest(unittest.TestCase):
    def run_setup(self, existing, remote_email='owner@example.test'):
        user = object()
        class Manager:
            def filter(self, **kwargs):
                self.assert_user(kwargs['user'])
                return existing
            def assert_user(self, actual):
                assert actual is user
            def create(self, **kwargs):
                existing.append(Integration(kwargs['server_url'], kwargs['api_key']))
        response = types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'email': remote_email})
        modules = {
            'requests': types.SimpleNamespace(get=lambda *a, **k: response),
            'django': types.ModuleType('django'),
            'django.contrib': types.ModuleType('django.contrib'),
            'django.contrib.auth': types.SimpleNamespace(get_user_model=lambda: types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda **k: user))),
            'integrations': types.ModuleType('integrations'),
            'integrations.models': types.SimpleNamespace(ImmichIntegration=types.SimpleNamespace(objects=Manager())),
        }
        with patch.dict(sys.modules, modules), patch.dict(os.environ, {'AL_IMMICH_URL': 'http://nas/api', 'AL_IMMICH_KEY': 'test-key', 'AL_ADMIN_EMAIL': 'owner@example.test'}), contextlib.redirect_stdout(io.StringIO()) as output:
            runpy.run_path(str(SCRIPT))
        return output.getvalue().strip()

    def test_creates_once_and_leaves_existing_unchanged(self):
        existing = []
        self.assertEqual(self.run_setup(existing), 'CHANGED')
        self.assertEqual(self.run_setup(existing), 'UNCHANGED')
        self.assertEqual(len(existing), 1)

    def test_rejects_key_for_another_immich_account(self):
        existing = []
        with self.assertRaisesRegex(RuntimeError, 'different email'):
            self.run_setup(existing, 'other@example.test')
        self.assertEqual(existing, [])

    def test_preserves_a_different_existing_server(self):
        existing = [Integration('http://other/api', 'old')]
        with self.assertRaisesRegex(RuntimeError, 'different server'):
            self.run_setup(existing)
        self.assertEqual(existing[0].api_key, 'old')
