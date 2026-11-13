"""Verify fleet management boundaries and private agent configuration."""
from pathlib import Path
import unittest

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
ANSIBLE = ROOT / 'builders/ansible'


class DockerManagementTest(unittest.TestCase):
    def test_agent_uses_host_token_and_tailnet_bind(self):
        role = ANSIBLE / 'roles/docker-agent'
        values = yaml.safe_load((role / 'defaults/main.yml').read_text())
        values.update(inventory_hostname='horizon', autolab_docker_agent_ip='100.64.0.11')
        template = jinja2.Environment(undefined=jinja2.StrictUndefined).from_string(
            (role / 'templates/docker-compose.yml.j2').read_text())
        services = yaml.safe_load(template.render(**values))['services']
        self.assertEqual(set(services), {'hawser'})
        self.assertEqual(services['hawser']['ports'], ['100.64.0.11:2376:2376'])
        self.assertEqual(services['hawser']['environment']['TOKEN_FILE'], '/run/secrets/hawser-token')
        self.assertIn('./secrets/hawser-token:/run/secrets/hawser-token:ro', services['hawser']['volumes'])
        self.assertIn('/opt/autolab:/opt/autolab', services['hawser']['volumes'])

    def test_playbook_excludes_tenants_and_hosts_without_docker(self):
        play = yaml.safe_load((ANSIBLE / 'playbooks/docker-management.yml').read_text())[0]
        self.assertIn("autolab_environment in ['lab', 'edge']", play['pre_tasks'][0]['ansible.builtin.assert']['that'])
        conditions = play['roles'][0]['when']
        self.assertTrue(any('docker_enabled' in condition for condition in conditions))
        self.assertIn("inventory_hostname != 'jwst'", conditions)
        self.assertIn('autolab_ssh_jump_host is not defined', conditions)

    def test_agent_project_does_not_install_docker_or_recreate_apps(self):
        tasks = yaml.safe_load((ANSIBLE / 'roles/docker-agent/tasks/main.yml').read_text())
        self.assertFalse(any('ansible.builtin.apt' in task for task in tasks))
        compose = next(t['community.docker.docker_compose_v2'] for t in tasks if 'community.docker.docker_compose_v2' in t)
        self.assertEqual(compose['project_name'], '{{ autolab_docker_agent_project }}')
        self.assertFalse(compose['remove_orphans'])
        self.assertEqual(compose['pull'], 'missing')
        self.assertTrue(any(t.get('ansible.builtin.uri', {}).get('status_code') == 401 for t in tasks))


if __name__ == '__main__':
    unittest.main()
