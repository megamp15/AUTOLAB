"""Every page a person can open is on both home and dash.

home (`home.<label>.<zone>`) and dash (`dash.<label>.<zone>`) are edited by
hand, so a service can be deployed and routed and still be on neither. This
fails when a catalog service with a port has no card or no tile, and when the
two pages list different things.
"""

import re
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
CATALOG = yaml.safe_load((ROOT / "builders/ansible/playbooks/group_vars/all.yml").read_text())["autolab_service_catalog"]
HOME = (ROOT / "builders/ansible/roles/observability-stack/defaults/main.yml").read_text()
DASH = (ROOT / "builders/ansible/roles/container-services/templates/dash/services.yaml.j2").read_text()

# A catalog service with a port and no page of its own. Each needs its reason;
# "it is only for admins" or "it is rarely used" is not one.
NO_PAGE = {
    "registry": "the Docker API, for `docker push`; its page is registry-ui",
    "immich-share": "serves shared links by key and nothing at its root",
    "code-server": "runs on no machine; the catalog entry and image build stay so one line can turn it back on",
}

# The same thing under two names, or a page that does not list itself.
HOME_ONLY = {"Dashboard"}  # dash, which does not link to itself
DASH_ONLY = {"Homepage"}  # home, which does not link to itself


def home_names():
    links = yaml.safe_load(HOME[HOME.index("autolab_obs_homepage_links:"):].split("\n\n")[0].replace("{{", "").replace("}}", ""))
    return {link["name"] for link in links["autolab_obs_homepage_links"]}


def dash_names():
    # Proxmox tiles come from the node list on both pages.
    return {name for name in re.findall(r"^    - (.+):$", DASH, re.MULTILINE) if not name.startswith("Proxmox")}


class EveryPageIsListedTest(unittest.TestCase):
    def pages(self):
        return [name for name, service in CATALOG.items() if "port" in service and name not in NO_PAGE]

    def test_every_service_with_a_page_has_a_home_card(self):
        for name in self.pages():
            with self.subTest(service=name):
                self.assertRegex(HOME, rf"name='{re.escape(name)}'|https://{re.escape(name)}\.\{{\{{ autolab_obs_public_zone",
                                 f"{name} has a port in the catalog and no card in autolab_obs_homepage_links")

    def test_every_service_with_a_page_has_a_dash_tile(self):
        for name in self.pages():
            if name == "dash":
                continue
            with self.subTest(service=name):
                self.assertRegex(DASH, rf"href: https://{re.escape(name)}\.\{{\{{ (lab|zone) \}}\}}",
                                 f"{name} has a port in the catalog and no tile in dash/services.yaml.j2")

    def test_home_and_dash_list_the_same_things(self):
        home, dash = home_names(), dash_names()
        self.assertEqual(home - dash, HOME_ONLY, "on home and not on dash")
        self.assertEqual(dash - home, DASH_ONLY, "on dash and not on home")

    def test_exemptions_are_still_real(self):
        for name in NO_PAGE:
            self.assertIn(name, CATALOG, f"{name} left the catalog; drop it from NO_PAGE")


if __name__ == "__main__":
    unittest.main()
