"""Every app's Pocket ID client reaches Ansible through workflow 05.

The workflow turns repository secrets into one JSON of role variables. A client
that is in the role's defaults but not in that JSON deploys with no login and
nothing fails: the role sees an empty client and skips Pocket ID. That shipped
once (#261). This is the check that it cannot happen again unnoticed.
"""
import re
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/05_ansible-builder.yml").read_text()
DEFAULTS = yaml.safe_load((ROOT / "builders/ansible/roles/container-services/defaults/main.yml").read_text())
CLIENT_VARS = sorted(k for k in DEFAULTS if re.fullmatch(r"autolab_services_[a-z]+_oidc_client_(id|secret)", k))


class WorkflowExtraVarsTest(unittest.TestCase):
    def test_there_are_clients_to_check(self):
        self.assertGreaterEqual(len(CLIENT_VARS), 12)

    def test_each_client_variable_is_in_the_extra_vars_json(self):
        for name in CLIENT_VARS:
            with self.subTest(name=name):
                self.assertIn(f'"{name}"', WORKFLOW)

    def test_each_client_variable_is_read_from_a_secret(self):
        for name in CLIENT_VARS:
            app, field = re.fullmatch(r"autolab_services_([a-z]+)_oidc_client_(id|secret)", name).groups()
            with self.subTest(name=name):
                upper = f"{app.upper()}_OIDC_CLIENT_{field.upper()}"
                self.assertIn(f"AUTOLAB_{upper}: ${{{{ secrets.{upper} }}}}", WORKFLOW)


if __name__ == "__main__":
    unittest.main()
