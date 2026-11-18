"""Check the actual ingress template keeps operator dashboards off the tunnel."""

import json
import re
from pathlib import Path
import unittest

import jinja2
import yaml


ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "builders/ansible/roles/ingress"


class PrivateDashboardTests(unittest.TestCase):
    def render(self, plugin=True, tailnet=True, service_hosts=None, public=None):
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        env.filters.update(bool=bool, to_json=json.dumps, b64decode=lambda value: value, trim=str.strip)
        defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
        defaults.update(
            autolab_ingress_zone="example.test",
            autolab_ingress_hostnames={"home": "home", "grafana": "grafana", "auth": "auth"},
            autolab_ingress_internal_label="lab",
            autolab_ingress_tailnet_side=tailnet,
            autolab_ingress_traefik_client_id="configured" if plugin else "",
            autolab_ingress_traefik_client_secret="test-only",
            autolab_ingress_oidc_plugin_secret="test-only",
            autolab_ingress_grafana_route=True,
            autolab_ingress_public_routes=public or {"share": {"upstream": "http://share:3000"}},
            autolab_ingress_internal_routes=defaults["autolab_ingress_service_routes"],
            autolab_ingress_services=list(service_hosts or {}),
            autolab_ingress_cosmos_token={"content": "test-only"},
            autolab_ingress_service_hosts=service_hosts or {},
            autolab_service_catalog=yaml.safe_load(
                (ROOT / "builders/ansible/playbooks/group_vars/all.yml").read_text())["autolab_service_catalog"],
        )
        template = env.from_string((ROLE / "templates/traefik-dynamic.yml.j2").read_text())
        return yaml.safe_load(template.render(**defaults))["http"]

    def test_public_entrypoint_excludes_dashboards(self):
        for plugin in (False, True):
            for tailnet in (False, True):
                with self.subTest(plugin=plugin, tailnet=tailnet):
                    routers = self.render(plugin, tailnet)["routers"]
                    public = {key for key, route in routers.items() if "web" in route["entryPoints"]}
                    self.assertEqual(public, {"auth", "public-share"})

    def test_private_routes_and_callback(self):
        config = self.render()
        for name in ("home", "grafana"):
            route = config["routers"][f"lab-{name}"]
            self.assertEqual(route["entryPoints"], ["tailnet-https"])
            self.assertEqual(route["rule"], f"Host(`{name}.lab.example.test`)")
            self.assertIn("tls", route)
        self.assertEqual(config["routers"]["lab-home"]["middlewares"], ["oidc"])
        self.assertNotIn("middlewares", config["routers"]["lab-grafana"])
        for middleware in ("oidc", "oidc-admin"):
            auth = config["middlewares"][middleware]["plugin"]["traefik-oidc-auth"]
            self.assertEqual(auth["CallbackUri"], "https://home.lab.example.test/oidc/callback")

    def test_service_on_another_machine_routes_there_and_never_to_the_tunnel(self):
        hosts = {"adventurelog": "nebula.tail.example", "registry-ui": "jwst.tail.example"}
        config = self.render(service_hosts=hosts)
        route = config["routers"]["lab-adventurelog"]
        self.assertEqual(route["entryPoints"], ["tailnet-https"])
        self.assertEqual(route["rule"], "Host(`adventurelog.lab.example.test`)")
        # It signs people in itself (Pocket ID), so no plugin in front of it.
        self.assertNotIn("middlewares", route)
        self.assertEqual(config["services"]["lab-adventurelog"]["loadBalancer"]["servers"],
                         [{"url": "http://nebula.tail.example:8098"}])
        self.assertEqual(config["services"]["lab-registry-ui"]["loadBalancer"]["servers"],
                         [{"url": "http://jwst.tail.example:8082"}])
        public = {key for key, r in config["routers"].items() if "web" in r["entryPoints"]}
        self.assertEqual(public, {"auth", "public-share"})

    def test_cosmos_ingest_skips_the_passkey_and_nothing_else_does(self):
        config = self.render(service_hosts={"cosmos": "jwst.tail.example"})
        site = config["routers"]["lab-cosmos"]
        self.assertEqual(site["rule"], "Host(`cosmos.lab.example.test`)")
        self.assertEqual(site["middlewares"], ["oidc-admin", "cosmos-upstream"])
        ingest = config["routers"]["lab-cosmos-token-paths"]
        self.assertEqual(ingest["rule"], "Host(`cosmos.lab.example.test`) && (PathPrefix(`/api/ingest/`))")
        # No login, but still the tailnet, the certificate and the gateway's credential.
        self.assertEqual(ingest["middlewares"], ["cosmos-upstream"])
        self.assertEqual(ingest["entryPoints"], ["tailnet-https"])
        self.assertEqual(ingest["service"], "lab-cosmos")
        self.assertIn("tls", ingest)
        # Without the login plugin the site has no route, so the open path has none either.
        self.assertNotIn("lab-cosmos-token-paths", self.render(plugin=False, service_hosts={"cosmos": "jwst.tail.example"})["routers"])

    def test_public_route_with_groups_is_behind_its_own_login(self):
        public = {"share": {"upstream": "http://share:3000"},
                  "qr": {"upstream": "http://jwst:8097", "groups": ["admins", "paradigm"]}}
        config = self.render(public=public)
        self.assertEqual(config["routers"]["public-qr"]["middlewares"], ["oidc-public-qr"])
        self.assertNotIn("middlewares", config["routers"]["public-share"])
        auth = config["middlewares"]["oidc-public-qr"]["plugin"]["traefik-oidc-auth"]
        self.assertEqual(auth["CallbackUri"], "https://qr.example.test/oidc/callback")
        self.assertEqual(auth["Authorization"]["AssertClaims"],
                         [{"Name": "groups", "AnyOf": ["admins", "paradigm"]}])
        # Its session is its own: another cookie name, and no Domain, so the
        # browser sends it to this one host and no internal route reads it.
        self.assertNotEqual(auth["CookieNamePrefix"], "TraefikOidcAuth")
        self.assertNotIn("Domain", auth["SessionCookie"])
        # No login configured: no route at all, never an open page.
        bare = self.render(plugin=False, public=public)
        self.assertNotIn("public-qr", bare["routers"])
        self.assertNotIn("public-qr", bare["services"])
        self.assertIn("public-share", bare["routers"])

    def test_every_login_checks_its_groups_on_each_request(self):
        # The plugin caches "allowed" in the session at login. Without this a
        # session made by one middleware passes another with stricter groups.
        public = {"qr": {"upstream": "http://jwst:8097", "groups": ["admins", "paradigm"]}}
        middlewares = self.render(public=public)["middlewares"]
        for name in ("oidc", "oidc-admin", "oidc-public-qr"):
            auth = middlewares[name]["plugin"]["traefik-oidc-auth"]
            self.assertIs(auth["Authorization"]["CheckOnEveryRequest"], True, name)

    def test_the_paradigm_group_opens_only_the_qr_page(self):
        play = yaml.safe_load((ROOT / "builders/ansible/playbooks/ingress.yml").read_text())[0]["vars"]
        self.assertEqual(play["autolab_ingress_public_routes"]["qr"]["groups"], ["admins", "paradigm"])
        self.assertNotIn("groups", play["autolab_ingress_public_routes"]["share"])
        role = (ROLE / "defaults/main.yml").read_text() + (ROLE / "templates/traefik-dynamic.yml.j2").read_text()
        self.assertNotIn("paradigm", role)

    def test_a_service_moved_to_a_public_name_has_no_lab_name(self):
        config = self.render(service_hosts={"qr": "jwst.tail.example", "dash": "jwst.tail.example"})
        self.assertNotIn("lab-qr", config["routers"])
        self.assertNotIn("lab-qr", config["services"])
        self.assertIn("lab-dash", config["routers"])

    def test_home_has_no_route_without_login(self):
        self.assertNotIn("lab-home", self.render(plugin=False)["routers"])

    def test_grafana_root_url_is_private(self):
        defaults = yaml.safe_load((ROLE.parent / "observability-stack/defaults/main.yml").read_text())
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        values = dict(defaults, autolab_obs_internal_label="lab", autolab_obs_public_zone="example.test")
        url = env.from_string(defaults["autolab_obs_grafana_url"]).render(**values).strip()
        self.assertEqual(url, "https://grafana.lab.example.test")

    def test_cloudflare_public_allowlist(self):
        source = (ROOT / "infra/stacks/cloudflare/ingress.auto.tfvars").read_text()
        labels = set(re.findall(r"^\s*(\w+)\s*=\s*\{\s*comment", source, re.MULTILINE))
        self.assertEqual(labels, {"auth", "share", "qr"})


if __name__ == "__main__":
    unittest.main()
