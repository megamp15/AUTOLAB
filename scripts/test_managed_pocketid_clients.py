import importlib.util
import json

import jinja2
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'builders/ansible/roles/container-services/files/managed_pocketid_clients.py'
spec = importlib.util.spec_from_file_location('managed_pocketid', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeApi:
    def __init__(self):
        self.client = None
        self.group = []
        self.secrets = []
        self.operations = []

    def request(self, method, path, data=None, allow_missing=False):
        self.operations.append((method, path))
        if path.startswith('/user-groups'):
            return {'data': [{'name': 'admins', 'id': 'admin-group'}]}
        if path.startswith('/oidc/clients?'):
            return {'data': []}
        if path == '/oidc/clients' and method == 'POST':
            self.client = dict(data, allowedUserGroups=[])
            return self.client
        if path.endswith('/allowed-user-groups'):
            self.group = [{'id': group} for group in data['userGroupIds']]
            self.client['allowedUserGroups'] = self.group
            return self.client
        if path.endswith('/secrets'):
            if method == 'GET':
                return self.secrets
            assert self.client['isGroupRestricted'] and self.group == [{'id': 'admin-group'}]
            self.secrets = [{'id': 'secret-id', 'expiresAt': None}]
            return {'id': 'secret-id'}
        if method == 'GET':
            return self.client
        if method == 'PUT':
            self.client.update(data)
            return self.client
        raise AssertionError((method, path))


class ProvisioningTest(unittest.TestCase):
    policy = {'group': 'admins', 'clients': {'adventurelog': {'callbacks': ['https://example.test/cb'], 'launch': 'https://example.test'}}}

    def test_creates_restricted_client_and_is_idempotent(self):
        api, state, snapshots = FakeApi(), {}, []
        save = lambda data: snapshots.append({k: dict(v) for k, v in data.items()})
        self.assertTrue(module.reconcile(api, self.policy, state, save))
        self.assertNotIn('secret_id', snapshots[0]['adventurelog'])
        self.assertEqual(state['adventurelog']['secret_id'], 'secret-id')
        self.assertFalse(module.reconcile(api, self.policy, state, save))
        self.assertEqual(len(api.secrets), 1)

    def test_unknown_secret_is_never_replaced(self):
        api = FakeApi()
        api.client = {'name': 'AUTOLAB adventurelog', 'isGroupRestricted': True, 'allowedUserGroups': [{'id': 'admin-group'}], 'isPublic': False, 'callbackURLs': ['https://example.test/cb'], 'launchURL': 'https://example.test'}
        api.secrets = [{'id': 'unexpected'}]
        state = {'adventurelog': {'id': 'x', 'secret': 'private'}}
        with self.assertRaisesRegex(RuntimeError, 'Unrecorded'):
            module.reconcile(api, self.policy, state, lambda _: None)
        self.assertEqual(api.secrets, [{'id': 'unexpected'}])

    def test_missing_state_never_adopts_or_duplicates_an_existing_client(self):
        api = FakeApi()
        original = api.request
        api.request = lambda method, path, *args, **kwargs: {'data': [{'name': 'AUTOLAB adventurelog'}]} if path.startswith('/oidc/clients?') else original(method, path, *args, **kwargs)
        with self.assertRaisesRegex(RuntimeError, 'state is missing'):
            module.reconcile(api, self.policy, {}, lambda _: None)
        self.assertIsNone(api.client)

    def test_missing_admin_group_prevents_creation(self):
        api = FakeApi()
        original = api.request
        api.request = lambda method, path, *args, **kwargs: {'data': []} if path.startswith('/user-groups') else original(method, path, *args, **kwargs)
        with self.assertRaisesRegex(RuntimeError, 'admins group'):
            module.reconcile(api, self.policy, {}, lambda _: None)
        self.assertIsNone(api.client)


class PolicyTest(unittest.TestCase):
    def test_policy_renders_six_restricted_client_callbacks(self):
        template = (path.parent.parent / 'templates/managed-pocketid-policy.json.j2').read_text()
        env = jinja2.Environment()
        env.filters['to_json'] = json.dumps
        names = ['adventurelog', 'forgejo', 'tandoor', 'airtrail', 'linkace', 'sure']
        values = {f'autolab_services_{name}_public_url': f'https://{name}.example.test' for name in names}
        values.update(autolab_services_enabled=names, autolab_services_oidc_issuer='https://auth.example.test', autolab_services_pocketid_group='admins')
        policy = json.loads(env.from_string(template).render(**values))
        self.assertEqual(set(policy['clients']), set(names))
        self.assertEqual(policy['group'], 'admins')
        self.assertEqual(policy['clients']['forgejo']['callbacks'], ['https://forgejo.example.test/user/oauth2/PocketID/callback'])
        self.assertEqual(policy['clients']['adventurelog']['callbacks'], ['https://adventurelog.example.test/accounts/oidc/pocketid/login/callback/'])
