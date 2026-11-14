import json
import unittest
from pathlib import Path

import jinja2


class BackupConfigTest(unittest.TestCase):
    def test_database_kind_is_forwarded_to_backup_script(self):
        template = Path('builders/ansible/roles/container-services/templates/db-backup.json.j2').read_text()
        env = jinja2.Environment()
        env.filters["to_json"] = json.dumps
        result = env.from_string(template).render(
            autolab_services_data_root='/mnt/apps',
            autolab_services_db_backup={'keep_daily': 14, 'keep_weekly_days': 60},
            autolab_services_db_names=['linkace', 'forgejo'],
            autolab_services_project='services',
            autolab_services_databases={
                'linkace': {'kind': 'mariadb', 'container': 'linkace-db', 'user': 'linkace', 'db': 'linkace', 'image': 'mariadb'},
                'forgejo': {'container': 'forgejo-db', 'user': 'forgejo', 'db': 'forgejo', 'image': 'postgres'},
            },
        )
        databases = json.loads(result)['databases']
        self.assertEqual(databases[0]['kind'], 'mariadb')
        self.assertEqual(databases[1]['kind'], 'postgres')
