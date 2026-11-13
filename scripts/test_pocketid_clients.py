"""Regression checks for preserving existing identities during URL migration."""

import copy
import json
import unittest

from pocketid_clients import POLICY, desired_clients, reconcile


class PocketIdClientsTests(unittest.TestCase):
    def setUp(self):
        self.current = {
            "id": "existing-id", "name": "Grafana",
            "callbackURLs": ["https://grafana.example.test/login/generic_oauth"],
            "logoutCallbackURLs": ["https://grafana.example.test/login"],
            "launchURL": "https://grafana.example.test",
            "credentials": {"secrets": [{"id": "keep-this-secret"}]},
            "allowedUserGroups": [{"id": "admins"}],
            "skipConsent": True, "pkceEnabled": False, "isGroupRestricted": True,
        }
        self.desired = {
            "callbackURLs": ["https://grafana.lab.example.test/login/generic_oauth"],
            "logoutCallbackURLs": ["https://grafana.lab.example.test/login"],
            "launchURL": "https://grafana.lab.example.test",
        }

    def test_prepare_keeps_running_callbacks_and_launch_url(self):
        result = reconcile(self.current, self.desired, prepare=True)
        for field in ("callbackURLs", "logoutCallbackURLs"):
            self.assertEqual(result[field], self.current[field] + self.desired[field])
        self.assertEqual(result["launchURL"], self.current["launchURL"])
        self.assertEqual(reconcile(result, self.desired, prepare=True), result)

    def test_apply_removes_old_callbacks_without_changing_identity_or_access(self):
        before = copy.deepcopy(self.current)
        result = reconcile(self.current, self.desired)
        for key, value in before.items():
            self.assertEqual(result[key], self.desired.get(key, value))
        self.assertEqual(self.current, before)
        self.assertEqual(reconcile(result, self.desired), result)

    def test_policy_uses_existing_ids_and_private_addresses(self):
        variables = {
            "autolab_ingress_hostnames": {"home": "home", "grafana": "grafana", "auth": "auth"},
            "autolab_ingress_zone": "example.test", "autolab_ingress_internal_label": "lab",
            "autolab_ingress_traefik_client_id": "existing-traefik",
            "autolab_obs_grafana_oidc_client_id": "existing-grafana",
        }
        clients = desired_clients(variables, json.loads(POLICY.read_text()))
        self.assertEqual(clients["traefik"][0], "existing-traefik")
        self.assertEqual(clients["grafana"][0], "existing-grafana")
        for _, settings in clients.values():
            self.assertIn(".lab.example.test", settings["launchURL"])
        variables["autolab_ingress_internal_label"] = ""
        with self.assertRaises(ValueError):
            desired_clients(variables, json.loads(POLICY.read_text()))


if __name__ == "__main__":
    unittest.main()
