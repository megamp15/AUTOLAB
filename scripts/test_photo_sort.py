#!/usr/bin/env python3
"""Run the real photo-sort scripts against a throwaway library, with a stand-in exiftool.

The stand-in reads recording months from a JSON map (path -> YYYY-MM), so the tests choose
exactly what each file claims to be, and need no real photos. Everything else (moves, name
clashes, duplicates, the CSV, the undo log) is the real code.
"""
import csv
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / 'builders/ansible/roles/nas-projects/files/photo-sort'

FAKE_EXIFTOOL = '''#!/usr/bin/env python3
import json, os, sys
dates = json.load(open(os.environ['FAKE_DATES']))
out = []
for p in sys.argv[1:]:
    if p.startswith('-') or p in ('QuickTimeUTC', '%Y-%m'):
        continue
    rel = os.path.relpath(p, os.environ['ROOT'])
    if rel in dates:
        out.append({'SourceFile': p, 'DateTimeOriginal': dates[rel]})
    else:
        out.append({'SourceFile': p})
print(json.dumps(out))
'''


class Library(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root, self.job, self.bin = self.tmp / 'media', self.tmp / 'job', self.tmp / 'bin'
        for d in (self.root, self.job, self.bin):
            d.mkdir()
        tool = self.bin / 'exiftool'
        tool.write_text(FAKE_EXIFTOOL)
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
        self.dates = {}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def put(self, rel, content, month=None):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content if isinstance(content, bytes) else content.encode())
        if month:
            self.dates[rel] = month
        return p

    def run_job(self, mode, **env):
        (self.tmp / 'dates.json').write_text(json.dumps(self.dates))
        full = {**os.environ, 'ROOT': str(self.root), 'JOB': str(self.job), 'MODE': mode,
                'PATH': f'{self.bin}:{os.environ["PATH"]}', 'FAKE_DATES': str(self.tmp / 'dates.json'), **env}
        r = subprocess.run([sys.executable, str(SRC / 'sort.py')], env=full, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def tree(self):
        return sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*') if p.is_file())


class LivePhotos(Library):
    def test_a_pair_stays_together_when_its_video_claims_the_next_month(self):
        # the MOV's own clock is a month after the HEIC's: the still decides for both
        self.put('_inbox/loose/IMG_1234.HEIC', 'still', '2025-06')
        self.put('_inbox/loose/IMG_1234.MOV', 'clip', '2025-07')
        self.run_job('apply')
        self.assertEqual(self.tree(), ['library/2025/06/IMG_1234.HEIC', 'library/2025/06/IMG_1234.MOV'])

    def test_a_name_clash_renames_both_halves_the_same_way(self):
        self.put('library/2025/06/IMG_1.HEIC', 'an older, different photo', '2025-06')
        self.put('_inbox/loose/IMG_1.HEIC', 'new still', '2025-06')
        self.put('_inbox/loose/IMG_1.MOV', 'new clip', '2025-06')
        self.run_job('apply')
        self.assertEqual(self.tree(), ['library/2025/06/IMG_1.HEIC', 'library/2025/06/IMG_1_1.HEIC',
                                       'library/2025/06/IMG_1_1.MOV'])

    def test_a_pair_whose_both_halves_are_already_sorted_goes_to_duplicates_together(self):
        self.put('library/2025/06/IMG_7.HEIC', 'same still', '2025-06')
        self.put('library/2025/06/IMG_7.MOV', 'same clip', '2025-06')
        self.put('_inbox/loose/IMG_7.HEIC', 'same still', '2025-06')
        self.put('_inbox/loose/IMG_7.MOV', 'same clip', '2025-06')
        self.run_job('apply')
        self.assertEqual(self.tree(), ['_duplicates/2025/06/IMG_7.HEIC', '_duplicates/2025/06/IMG_7.MOV',
                                       'library/2025/06/IMG_7.HEIC', 'library/2025/06/IMG_7.MOV'])

    def test_a_pair_with_one_new_half_is_kept_whole_not_split(self):
        # the still is a copy of one already sorted, the clip is new: neither is dropped
        self.put('library/2025/06/IMG_8.HEIC', 'same still', '2025-06')
        self.put('_inbox/loose/IMG_8.HEIC', 'same still', '2025-06')
        self.put('_inbox/loose/IMG_8.MOV', 'a clip nobody has', '2025-06')
        self.run_job('apply')
        self.assertEqual(self.tree(), ['library/2025/06/IMG_8.HEIC', 'library/2025/06/IMG_8_1.HEIC',
                                       'library/2025/06/IMG_8_1.MOV'])

    def test_files_that_only_share_a_stem_in_different_folders_are_not_a_pair(self):
        self.put('_inbox/loose/a/IMG_9.HEIC', 'still', '2025-06')
        self.put('_inbox/loose/b/IMG_9.MOV', 'clip', '2025-08')
        self.run_job('apply')
        self.assertEqual(self.tree(), ['library/2025/06/IMG_9.HEIC', 'library/2025/08/IMG_9.MOV'])

    def test_a_pair_merged_into_an_existing_event_keeps_one_name(self):
        self.put('library/2025/06/Trip/IMG_3.HEIC', 'different photo', '2025-06')
        self.put('_inbox/events/Trip/IMG_3.HEIC', 'new still', '2025-06')
        self.put('_inbox/events/Trip/IMG_3.MOV', 'new clip', '2025-06')
        self.run_job('apply')
        self.assertEqual(self.tree(), ['library/2025/06/Trip/IMG_3.HEIC', 'library/2025/06/Trip/IMG_3_1.HEIC',
                                       'library/2025/06/Trip/IMG_3_1.MOV'])

    def test_a_sidecar_follows_each_half(self):
        self.put('_inbox/loose/IMG_5.HEIC', 'still', '2025-06')
        self.put('_inbox/loose/IMG_5.MOV', 'clip', '2025-06')
        self.put('_inbox/loose/IMG_5.HEIC.xmp', 'meta')
        self.run_job('apply')
        self.assertIn('library/2025/06/IMG_5.HEIC.xmp', self.tree())


class Unchanged(Library):
    """Without pairs the sorter does what it always did."""

    def test_lone_files_are_sorted_each_by_its_own_date(self):
        self.put('_inbox/loose/IMG_1.JPG', 'a', '2025-06')
        self.put('_inbox/loose/IMG_2.MOV', 'b', '2025-07')
        self.put('_inbox/loose/undated.JPG', 'c')
        self.run_job('apply')
        self.assertEqual(self.tree(), ['_no_date/_inbox/loose/undated.JPG',
                                       'library/2025/06/IMG_1.JPG', 'library/2025/07/IMG_2.MOV'])

    def test_a_single_name_clash_still_gets_a_suffix(self):
        self.put('library/2025/06/IMG_1.JPG', 'old', '2025-06')
        self.put('_inbox/loose/IMG_1.JPG', 'new', '2025-06')
        self.run_job('apply')
        self.assertEqual(self.tree(), ['library/2025/06/IMG_1.JPG', 'library/2025/06/IMG_1_1.JPG'])

    def test_plan_changes_nothing(self):
        self.put('_inbox/loose/IMG_1.HEIC', 'a', '2025-06')
        self.put('_inbox/loose/IMG_1.MOV', 'b', '2025-06')
        before = self.tree()
        self.run_job('plan')
        self.assertEqual(self.tree(), before)
        self.assertTrue((self.job / 'plan.txt').read_text().count('\n') >= 2)


class DuplicateCleanup(Library):
    def report(self):
        self.run_job('dupes')
        return list(csv.DictReader(open(self.job / 'duplicates.csv')))

    def set_keep(self, rows):
        with open(self.job / 'duplicates.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['group', 'sha1', 'size_mb', 'keep', 'path'])
            w.writeheader()
            w.writerows(rows)

    def test_a_half_is_left_alone_when_its_partner_is_kept(self):
        # copy A is a whole pair; copy B has the same still, but its clip is unique
        self.put('library/2025/06/A/IMG_1.HEIC', 'same still')
        self.put('library/2025/06/A/IMG_1.MOV', 'clip A')
        self.put('library/2025/06/B/IMG_1.HEIC', 'same still')
        self.put('library/2025/06/B/IMG_1.MOV', 'a different clip')
        rows = self.report()
        self.assertEqual(len(rows), 2)   # only the stills are byte-identical
        self.run_job('dupes-apply')
        self.assertEqual(self.tree(), ['library/2025/06/A/IMG_1.HEIC', 'library/2025/06/A/IMG_1.MOV',
                                       'library/2025/06/B/IMG_1.HEIC', 'library/2025/06/B/IMG_1.MOV'])

    def test_both_halves_marked_no_are_filed_together(self):
        for d in ('A', 'B'):
            self.put(f'library/2025/06/{d}/IMG_1.HEIC', 'same still')
            self.put(f'library/2025/06/{d}/IMG_1.MOV', 'same clip')
        rows = self.report()
        self.assertEqual(len(rows), 4)
        self.run_job('dupes-apply')
        moved = [t for t in self.tree() if t.startswith('_duplicates/')]
        self.assertEqual(len(moved), 2)
        self.assertEqual({Path(t).stem for t in moved}, {'IMG_1'})   # the still and the clip, one name
        self.assertEqual(len([t for t in self.tree() if t.startswith('library/')]), 2)

    def test_unpaired_duplicates_are_still_filed(self):
        self.put('library/2025/06/A/IMG_2.JPG', 'same')
        self.put('library/2025/06/B/IMG_2.JPG', 'same')
        self.report()
        self.run_job('dupes-apply')
        self.assertEqual(len([t for t in self.tree() if t.startswith('_duplicates/')]), 1)


if __name__ == '__main__':
    unittest.main()
