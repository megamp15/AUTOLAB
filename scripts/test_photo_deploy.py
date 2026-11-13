"""The photo service's deployment: what is rendered for the NAS and for Traefik.

The two properties that matter: nothing is deployed or routed without the shared token, and the
route is Pocket ID admins only with that token added after login.
"""
import json
import unittest
from pathlib import Path

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
ANSIBLE = ROOT / 'builders/ansible'
TOKEN = 'a' * 64


def render(path, **values):
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    env.filters['to_json'] = json.dumps
    env.filters['bool'] = bool
    return env.from_string((ANSIBLE / path).read_text()).render(**values)


class NasCompose(unittest.TestCase):
    def setUp(self):
        role = yaml.safe_load((ANSIBLE / 'roles/nas-photos/defaults/main.yml').read_text())
        role.update(autolab_photos_ip='100.64.0.9', autolab_photos_token=TOKEN)
        self.role = role
        self.compose = yaml.safe_load(render('roles/nas-photos/templates/docker-compose.yml.j2', **role))
        self.service = self.compose['services']['photo-jobs']

    def test_the_token_is_in_a_private_env_file_not_the_compose_file(self):
        self.assertEqual(self.service['env_file'], ['.env'])
        self.assertNotIn(TOKEN, json.dumps(self.compose))
        self.assertEqual(render('roles/nas-photos/templates/env.j2', **self.role).strip(), f'PHOTO_JOBS_TOKEN={TOKEN}')
        tasks = yaml.safe_load((ANSIBLE / 'roles/nas-photos/tasks/main.yml').read_text())
        env_task = next(t for t in tasks if t.get('name', '').startswith('Render the compose'))
        self.assertEqual(next(i for i in env_task['loop'] if i['dest'] == '.env')['mode'], '0600')

    def test_it_listens_on_the_tailnet_address_only(self):
        self.assertEqual(self.service['ports'], ['100.64.0.9:8099:8099'])

    def test_the_media_folder_is_mounted_writable_and_state_is_separate(self):
        self.assertIn('/home/Mahir/media:/media', self.service['volumes'])
        self.assertTrue(any(v.endswith(':/state') for v in self.service['volumes']))

    def test_the_play_stops_without_a_token_before_creating_anything(self):
        tasks = yaml.safe_load((ANSIBLE / 'roles/nas-photos/tasks/main.yml').read_text())
        self.assertIn('autolab_photos_token | length >= 32', json.dumps(tasks[0]))
        self.assertTrue(tasks[0]['no_log'])

    def test_it_proves_the_api_refuses_a_request_without_the_token(self):
        tasks = yaml.safe_load((ANSIBLE / 'roles/nas-photos/tasks/main.yml').read_text())
        refused = [t for t in tasks if t.get('ansible.builtin.uri', {}).get('status_code') == 401]
        self.assertEqual(len(refused), 1)
        self.assertNotIn('headers', refused[0]['ansible.builtin.uri'])

    def test_it_proves_immich_was_left_alone(self):
        tasks = yaml.safe_load((ANSIBLE / 'roles/nas-photos/tasks/main.yml').read_text())
        self.assertIn('autolab_photos_before.stdout_lines == autolab_photos_after.stdout_lines', json.dumps(tasks[-1]))

    def test_the_build_context_is_the_app_and_only_the_app(self):
        tasks = yaml.safe_load((ANSIBLE / 'roles/nas-photos/tasks/main.yml').read_text())
        copy = next(t for t in tasks if t.get('name', '').startswith('Copy the build context'))
        self.assertEqual([i['src'] for i in copy['loop']], ['Dockerfile', 'photo_jobs/', 'web/'])
        for name in ('Dockerfile', 'photo_jobs', 'web'):
            self.assertTrue((ROOT / 'apps/photo-jobs' / name).exists(), name)


class IngressRoute(unittest.TestCase):
    def render(self, photos):
        routes = {'pihole': {'upstream': 'http://magnetosphere:8053', 'login': 'plugin'}}
        if photos:
            routes['photos'] = {'upstream': 'http://singularity:8099', 'login': 'admin',
                                'token_header': 'X-Autolab-Photos-Token', 'token': TOKEN}
        doc = render('roles/ingress/templates/traefik-dynamic.yml.j2',
                     autolab_ingress_zone='example.com', autolab_ingress_hostnames={'auth': 'auth', 'home': 'home'},
                     autolab_ingress_traefik_client_id='id', autolab_ingress_traefik_client_secret='secret',
                     autolab_ingress_tailnet_side=True, autolab_ingress_internal_label='lab',
                     autolab_ingress_public_routes={}, autolab_ingress_internal_routes=routes,
                     autolab_ingress_services=[], autolab_service_catalog={},
                     autolab_ingress_upstreams={'homepage': 'http://h:8080'}, autolab_ingress_homepage_groups=['admins'],
                     autolab_ingress_oidc_plugin_secret='s', autolab_ingress_session_max_age=1)
        return yaml.safe_load(doc)['http']

    def test_the_route_is_admins_only_with_the_token_added_after_login(self):
        http = self.render(True)
        router = http['routers']['lab-photos']
        self.assertEqual(router['rule'], 'Host(`photos.lab.example.com`)')
        self.assertEqual(router['middlewares'], ['oidc-admin', 'lab-photos-token'])   # login first, then the token
        self.assertEqual(http['middlewares']['lab-photos-token']['headers']['customRequestHeaders'],
                         {'X-Autolab-Photos-Token': TOKEN})
        self.assertEqual(http['services']['lab-photos']['loadBalancer']['servers'], [{'url': 'http://singularity:8099'}])

    def test_other_routes_are_unchanged(self):
        http = self.render(True)
        self.assertEqual(http['routers']['lab-pihole']['middlewares'], ['oidc'])
        self.assertNotIn('lab-pihole-token', http['middlewares'])

    def test_there_is_no_route_at_all_without_the_token(self):
        http = self.render(False)
        self.assertNotIn('lab-photos', http['routers'])
        self.assertNotIn('lab-photos-token', http['middlewares'])

    def test_the_playbook_only_adds_the_route_when_the_token_exists(self):
        play = (ANSIBLE / 'playbooks/ingress.yml').read_text()
        self.assertIn('if autolab_ingress_photos_token | length > 0 else {}', play)


class Image(unittest.TestCase):
    def test_the_dockerfile_installs_exiftool_and_runs_the_service(self):
        text = (ROOT / 'apps/photo-jobs/Dockerfile').read_text()
        self.assertRegex(text, r'FROM python:3\.12\.\d+-alpine')   # pinned, not a floating tag
        self.assertIn('exiftool', text)
        self.assertIn('photo_jobs.server', text)

    def test_dev_files_stay_out_of_the_image(self):
        ignored = (ROOT / 'apps/photo-jobs/.dockerignore').read_text().split()
        self.assertIn('dev', ignored)


if __name__ == '__main__':
    unittest.main()
