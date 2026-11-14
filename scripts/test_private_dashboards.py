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
    def render(self, plugin=True, tailnet=True, service_hosts=None):
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        env.filters.update(bool=bool, to_json=json.dumps)
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
            autolab_ingress_public_routes={"share": {"upstream": "http://share:3000"}},
            autolab_ingress_internal_routes=defaults["autolab_ingress_service_routes"],
            autolab_ingress_services=list(service_hosts or {}),
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
        self.assertEqual(labels, {"auth", "share"})


if __name__ == "__main__":
    unittest.main()
