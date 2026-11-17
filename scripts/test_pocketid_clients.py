"""Regression checks for preserving existing identities during URL migration."""

import copy
import json
import unittest

from types import SimpleNamespace

from pocketid_clients import POLICY, desired_clients, group_changes, reconcile, reconcile_groups


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
        policy = json.loads(POLICY.read_text())
        # Without a way to ask Pocket ID, clients adopted by name are left out.
        self.assertEqual(set(desired_clients(variables, policy)), {"traefik", "grafana"})
        clients = desired_clients(variables, policy, find=lambda name: "found-" + name)
        self.assertEqual(clients["traefik"][0], "existing-traefik")
        self.assertEqual(clients["grafana"][0], "existing-grafana")
        for name in ("traefik", "grafana"):
            self.assertIn(".lab.example.test", clients[name][1]["launchURL"])
        for _, settings, _ in clients.values():
            self.assertNotIn("allowedUserGroups", settings)
        # The plugin's client declares who may sign in through it; Grafana's
        # declares nothing, so its groups stay as Pocket ID has them.
        self.assertEqual(clients["traefik"][2], ["admins", "paradigm"])
        # Hand-made clients no secret of ours names: adopted by display name,
        # groups only, so their URLs stay as Pocket ID has them.
        for name, display in (("proxmox", "Proxmox"), ("immich", "Immich")):
            self.assertEqual(clients[name], ("found-" + display, {}, ["admins"]))
        self.assertEqual(clients["grafana"][2], ["admins"])
        self.assertEqual(set(desired_clients(variables, policy, find=lambda name: "x", only={"immich"})), {"immich"})
        self.assertIn("https://qr.example.test/oidc/callback", clients["traefik"][1]["callbackURLs"])
        variables["autolab_ingress_internal_label"] = ""
        with self.assertRaises(ValueError):
            desired_clients(variables, policy)

    def test_declared_groups_are_created_and_made_the_only_ones_allowed(self):
        existing = [{"id": "1", "name": "admins"}, {"id": "2", "name": "viewers"}]
        wanted = ["admins", "viewers", "paradigm"]  # any list; the policy's own is checked above
        client = {"isGroupRestricted": True, "allowedUserGroups": existing}
        self.assertEqual(group_changes(existing, wanted, client), (["paradigm"], True))
        everyone = existing + [{"id": "3", "name": "paradigm"}]
        self.assertEqual(group_changes(everyone, wanted, dict(client, allowedUserGroups=everyone)), ([], False))
        # The right groups on a client that admits anyone is still a difference.
        open_client = {"isGroupRestricted": False, "allowedUserGroups": everyone}
        self.assertEqual(group_changes(everyone, wanted, open_client), ([], True))
        # A group allowed in Pocket ID but not declared is a difference too.
        extra = everyone + [{"id": "4", "name": "guests"}]
        self.assertTrue(group_changes(extra, wanted, dict(client, allowedUserGroups=extra))[1])

    def fake_pocket_id(self):
        """Pocket ID as far as groups go, with its habit of clearing an unrestricted client's groups."""
        test = self

        class Fake:
            def __init__(self):
                self.groups = [{"id": "1", "name": "admins"}, {"id": "2", "name": "viewers"}]
                self.client = {"id": "c", "isGroupRestricted": False, "allowedUserGroups": []}
                self.writes = []

            def call(self, method, path, body=None):
                if method == "GET":
                    return {"data": list(self.groups)}
                self.writes.append("create " + body["name"])
                self.groups.append({"id": str(len(self.groups) + 1), "name": body["name"]})
                return self.groups[-1]

            def request(self, method, client_id, body=None, suffix=""):
                if method == "PUT" and suffix:
                    self.writes.append("allow")
                    self.client["allowedUserGroups"] = [g for g in self.groups if g["id"] in body["userGroupIds"]]
                elif method == "PUT":
                    self.writes.append("restrict")
                    test.assertTrue(body["isGroupRestricted"])
                    self.client = copy.deepcopy(body)
                return copy.deepcopy(self.client)

        return Fake()

    def test_group_reconcile_by_mode(self):
        wanted = ["admins", "viewers", "paradigm"]
        check = self.fake_pocket_id()
        reconcile_groups(check, "traefik", "c", wanted, SimpleNamespace(apply=False, prepare=False))
        self.assertEqual(check.writes, [])
        prepare = self.fake_pocket_id()
        reconcile_groups(prepare, "traefik", "c", wanted, SimpleNamespace(apply=False, prepare=True))
        self.assertEqual(prepare.writes, ["create paradigm"])
        apply = self.fake_pocket_id()
        mode = SimpleNamespace(apply=True, prepare=False)
        reconcile_groups(apply, "traefik", "c", wanted, mode)
        # Groups before the restriction: never a restricted client with none.
        self.assertEqual(apply.writes, ["create paradigm", "allow", "restrict"])
        self.assertEqual({g["name"] for g in apply.client["allowedUserGroups"]}, set(wanted))
        apply.writes.clear()
        reconcile_groups(apply, "traefik", "c", wanted, mode)
        self.assertEqual(apply.writes, [])
        with self.assertRaises(ValueError):
            reconcile_groups(apply, "traefik", "c", [], mode)


if __name__ == "__main__":
    unittest.main()
