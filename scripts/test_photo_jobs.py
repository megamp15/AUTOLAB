#!/usr/bin/env python3
"""Photo Jobs against a throwaway library, with a stand-in exiftool.

The stand-in reads recording months from a JSON map (path -> YYYY-MM), so each test chooses what
every file claims to be, and needs no real photos. Planning, applying, undoing and the HTTP routes
are the real code.
"""
import base64
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'apps/photo-jobs'
sys.path.insert(0, str(APP))

sys.path.insert(0, str(APP / 'dev'))

from fake_immich import FakeImmich, sha1b64  # noqa: E402
from photo_jobs import core, immich, jobs, metadata, nodate, pairs, previews, server  # noqa: E402

FAKE_EXIFTOOL = (APP / 'dev/fake_exiftool.py').read_text()


class Library(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root, self.state, self.bin = self.tmp / 'media', self.tmp / 'state', self.tmp / 'bin'
        for d in (self.root, self.state, self.bin):
            d.mkdir()
        tool = self.bin / 'exiftool'
        tool.write_text(FAKE_EXIFTOOL)
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
        self.dates = {}
        self.cfg = core.Config(self.root, self.state)
        self.old_env = dict(os.environ)
        os.environ.update(PATH=f'{self.bin}:{os.environ["PATH"]}', FAKE_DATES=str(self.tmp / 'dates.json'),
                          ROOT=str(self.cfg.root))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_env)
        shutil.rmtree(self.tmp)

    def put(self, rel, content, month=None):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content if isinstance(content, bytes) else content.encode())
        if month:
            self.dates[rel] = month
        return p

    def sync_dates(self):
        (self.tmp / 'dates.json').write_text(json.dumps(self.dates))

    def sort(self):
        """Plan the inbox and apply every move, as the page does with nothing unticked."""
        self.sync_dates()
        plan = core.plan_sort(self.cfg)
        plan.update(excluded=[], excluded_kinds=[])
        run = core.apply_moves(self.cfg, core.selected_moves(plan, self.cfg))
        return plan, run

    def tree(self):
        return sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*') if p.is_file())


class LivePhotos(Library):
    def test_a_pair_stays_together_when_its_clip_claims_the_next_month(self):
        self.put('_inbox/loose/IMG_1234.HEIC', 'still', '2025-06')
        self.put('_inbox/loose/IMG_1234.MOV', 'clip', '2025-07')
        self.sort()
        self.assertEqual(self.tree(), ['library/2025/06/IMG_1234.HEIC', 'library/2025/06/IMG_1234.MOV'])

    def test_a_name_clash_renames_both_halves_the_same_way(self):
        self.put('library/2025/06/IMG_1.HEIC', 'an older, different photo', '2025-06')
        self.put('_inbox/loose/IMG_1.HEIC', 'new still', '2025-06')
        self.put('_inbox/loose/IMG_1.MOV', 'new clip', '2025-06')
        self.sort()
        self.assertEqual(self.tree(), ['library/2025/06/IMG_1.HEIC', 'library/2025/06/IMG_1_1.HEIC',
                                       'library/2025/06/IMG_1_1.MOV'])

    def test_a_pair_whose_both_halves_are_already_sorted_goes_to_duplicates_together(self):
        for f, c in (('HEIC', 'same still'), ('MOV', 'same clip')):
            self.put(f'library/2025/06/IMG_7.{f}', c, '2025-06')
            self.put(f'_inbox/loose/IMG_7.{f}', c, '2025-06')
        self.sort()
        self.assertEqual(self.tree(), ['_duplicates/2025/06/IMG_7.HEIC', '_duplicates/2025/06/IMG_7.MOV',
                                       'library/2025/06/IMG_7.HEIC', 'library/2025/06/IMG_7.MOV'])

    def test_a_pair_with_one_new_half_is_kept_whole_not_split(self):
        self.put('library/2025/06/IMG_8.HEIC', 'same still', '2025-06')
        self.put('_inbox/loose/IMG_8.HEIC', 'same still', '2025-06')
        self.put('_inbox/loose/IMG_8.MOV', 'a clip nobody has', '2025-06')
        self.sort()
        self.assertEqual(self.tree(), ['library/2025/06/IMG_8.HEIC', 'library/2025/06/IMG_8_1.HEIC',
                                       'library/2025/06/IMG_8_1.MOV'])

    def test_files_that_only_share_a_stem_in_different_folders_are_not_a_pair(self):
        self.put('_inbox/loose/a/IMG_9.HEIC', 'still', '2025-06')
        self.put('_inbox/loose/b/IMG_9.MOV', 'clip', '2025-08')
        self.sort()
        self.assertEqual(self.tree(), ['library/2025/06/IMG_9.HEIC', 'library/2025/08/IMG_9.MOV'])

    def test_a_pair_merged_into_an_existing_event_keeps_one_name(self):
        self.put('library/2025/06/Trip/IMG_3.HEIC', 'different photo', '2025-06')
        self.put('_inbox/events/Trip/IMG_3.HEIC', 'new still', '2025-06')
        self.put('_inbox/events/Trip/IMG_3.MOV', 'new clip', '2025-06')
        self.sort()
        self.assertEqual(self.tree(), ['library/2025/06/Trip/IMG_3.HEIC', 'library/2025/06/Trip/IMG_3_1.HEIC',
                                       'library/2025/06/Trip/IMG_3_1.MOV'])

    def test_a_sidecar_follows_each_half(self):
        self.put('_inbox/loose/IMG_5.HEIC', 'still', '2025-06')
        self.put('_inbox/loose/IMG_5.MOV', 'clip', '2025-06')
        self.put('_inbox/loose/IMG_5.HEIC.xmp', 'meta')
        self.sort()
        self.assertIn('library/2025/06/IMG_5.HEIC.xmp', self.tree())

    def test_the_two_halves_are_one_group_so_they_are_ticked_together(self):
        self.put('_inbox/loose/IMG_1.HEIC', 'still', '2025-06')
        self.put('_inbox/loose/IMG_1.MOV', 'clip', '2025-06')
        self.sync_dates()
        plan = core.plan_sort(self.cfg)
        self.assertEqual({m['group'] for m in plan['moves']}, {'pair:_inbox/loose/IMG_1.HEIC'})
        plan.update(excluded=['pair:_inbox/loose/IMG_1.HEIC'], excluded_kinds=[])
        self.assertEqual(core.selected_moves(plan, self.cfg), [])


class Unchanged(Library):
    def test_lone_files_are_sorted_each_by_its_own_date(self):
        self.put('_inbox/loose/IMG_1.JPG', 'a', '2025-06')
        self.put('_inbox/loose/IMG_2.MOV', 'b', '2025-07')
        self.put('_inbox/loose/undated.JPG', 'c')
        self.sort()
        self.assertEqual(self.tree(), ['_no_date/_inbox/loose/undated.JPG',
                                       'library/2025/06/IMG_1.JPG', 'library/2025/07/IMG_2.MOV'])

    def test_a_single_name_clash_still_gets_a_suffix(self):
        self.put('library/2025/06/IMG_1.JPG', 'old', '2025-06')
        self.put('_inbox/loose/IMG_1.JPG', 'new', '2025-06')
        self.sort()
        self.assertEqual(self.tree(), ['library/2025/06/IMG_1.JPG', 'library/2025/06/IMG_1_1.JPG'])

    def test_two_copies_in_one_inbox_become_one_photo_and_one_duplicate(self):
        self.put('_inbox/loose/a/IMG_1.JPG', 'same', '2025-06')
        self.put('_inbox/loose/b/IMG_1.JPG', 'same', '2025-06')
        self.sort()
        self.assertEqual(self.tree(), ['_duplicates/2025/06/IMG_1.JPG', 'library/2025/06/IMG_1.JPG'])

    def test_an_event_moves_whole_into_its_main_month(self):
        for i in range(3):
            self.put(f'_inbox/events/Beach/IMG_{i}.JPG', f'p{i}', '2025-07')
        self.put('_inbox/events/Beach/IMG_9.JPG', 'stray', '2025-08')
        self.sort()
        self.assertEqual(len([t for t in self.tree() if t.startswith('library/2025/07/Beach/')]), 4)

    def test_an_event_that_started_the_month_before_goes_there(self):
        for i in range(3):
            self.put(f'_inbox/events/Trip/A{i}.JPG', f'a{i}', '2025-06')
        for i in range(4):
            self.put(f'_inbox/events/Trip/B{i}.JPG', f'b{i}', '2025-07')
        self.sort()
        self.assertTrue(all(t.startswith('library/2025/06/Trip/') for t in self.tree()))

    def test_a_folder_dropped_in_loose_is_flattened_into_the_recording_month(self):
        self.put('_inbox/loose/uploaded-folder/photo.jpg', 'example photo', '2026-09')
        self.sort()
        self.assertEqual(self.tree(), ['library/2026/09/photo.jpg'])

    def test_a_named_event_stays_grouped_and_uses_recording_dates(self):
        self.put('_inbox/events/Trip/a.jpg', 'photo a', '2026-09')
        self.put('_inbox/events/Trip/b.jpg', 'photo b', '2026-09')
        self.sort()
        self.assertEqual(self.tree(), ['library/2026/09/Trip/a.jpg', 'library/2026/09/Trip/b.jpg'])

    def test_planning_changes_nothing(self):
        self.put('_inbox/loose/IMG_1.HEIC', 'a', '2025-06')
        self.put('_inbox/loose/IMG_1.MOV', 'b', '2025-06')
        self.sync_dates()
        before = self.tree()
        plan = core.plan_sort(self.cfg)
        self.assertEqual(self.tree(), before)
        self.assertEqual(plan['stats']['moves'], 2)
        self.assertEqual(plan['stats']['pairs'], 1)


class ApplyAndUndo(Library):
    def test_unticked_moves_are_not_made(self):
        self.put('_inbox/loose/IMG_1.JPG', 'a', '2025-06')
        self.put('_inbox/loose/IMG_2.JPG', 'b', '2025-06')
        self.sync_dates()
        plan = core.plan_sort(self.cfg)
        skip = next(m for m in plan['moves'] if m['src'].endswith('IMG_2.JPG'))
        plan.update(excluded=[f'm{skip["id"]}'], excluded_kinds=[])
        core.apply_moves(self.cfg, core.selected_moves(plan, self.cfg))
        self.assertEqual(self.tree(), ['_inbox/loose/IMG_2.JPG', 'library/2025/06/IMG_1.JPG'])

    def test_a_whole_kind_can_be_unticked(self):
        self.put('_inbox/loose/IMG_1.JPG', 'a', '2025-06')
        self.put('_inbox/loose/undated.JPG', 'b')
        self.sync_dates()
        plan = core.plan_sort(self.cfg)
        plan.update(excluded=[], excluded_kinds=['no date'])
        core.apply_moves(self.cfg, core.selected_moves(plan, self.cfg))
        self.assertEqual(self.tree(), ['_inbox/loose/undated.JPG', 'library/2025/06/IMG_1.JPG'])

    def test_apply_does_what_the_plan_says_and_skips_what_changed_since(self):
        self.put('_inbox/loose/IMG_1.JPG', 'a', '2025-06')
        self.put('_inbox/loose/IMG_2.JPG', 'b', '2025-06')
        self.sync_dates()
        plan = core.plan_sort(self.cfg)
        (self.root / '_inbox/loose/IMG_1.JPG').unlink()                  # gone since the plan
        self.put('library/2025/06/IMG_2.JPG', 'someone else got there')   # destination taken since
        run = core.apply_moves(self.cfg, plan['moves'])
        self.assertEqual(sorted(m['status'] for m in run['moves']), ['skipped', 'skipped'])
        self.assertEqual(self.tree(), ['_inbox/loose/IMG_2.JPG', 'library/2025/06/IMG_2.JPG'])

    def test_nothing_is_ever_overwritten(self):
        self.put('_inbox/loose/IMG_1.JPG', 'new', '2025-06')
        self.sync_dates()
        plan = core.plan_sort(self.cfg)
        victim = self.put(plan['moves'][0]['dst'], 'precious')
        core.apply_moves(self.cfg, plan['moves'])
        self.assertEqual(victim.read_text(), 'precious')

    def test_undo_puts_everything_back_and_removes_the_folders_it_made(self):
        self.put('_inbox/loose/IMG_1.HEIC', 'a', '2025-06')
        self.put('_inbox/loose/IMG_1.MOV', 'b', '2025-06')
        self.put('_inbox/events/Beach/IMG_2.JPG', 'c', '2025-07')
        before = self.tree()
        _, run = self.sort()
        self.assertNotEqual(self.tree(), before)
        result = core.undo_run(self.cfg, run)
        self.assertEqual(self.tree(), before)
        self.assertEqual(result['restored'], 3)
        self.assertFalse((self.root / 'library/2025').exists())

    def test_undo_leaves_alone_what_has_since_changed(self):
        self.put('_inbox/loose/IMG_1.JPG', 'a', '2025-06')
        _, run = self.sort()
        (self.root / 'library/2025/06/IMG_1.JPG').unlink()
        result = core.undo_run(self.cfg, run)
        self.assertEqual(result['restored'], 0)
        self.assertEqual(len(result['skipped']), 1)

    def test_paths_outside_the_media_folder_are_refused(self):
        with self.assertRaises(ValueError):
            self.cfg.abs('../etc/passwd')


class Duplicates(Library):
    def plan(self):
        plan = core.plan_duplicates(self.cfg)
        plan.update(excluded=[], excluded_kinds=[])
        return plan

    def test_the_copy_in_an_event_is_kept_over_a_loose_one(self):
        self.put('library/2025/06/IMG_1.JPG', 'same')
        self.put('library/2025/06/Trip/IMG_1.JPG', 'same')
        plan = self.plan()
        self.assertEqual(plan['groups'][0]['keep'], 'library/2025/06/Trip/IMG_1.JPG')

    def test_the_keeper_can_be_changed_and_the_others_are_filed_beside_it(self):
        self.put('library/2025/06/A/IMG_1.JPG', 'same')
        self.put('library/2025/06/B/IMG_1.JPG', 'same')
        plan = self.plan()
        plan['groups'][0]['keep'] = 'library/2025/06/B/IMG_1.JPG'
        moves = core.selected_moves(plan, self.cfg)
        self.assertEqual([(m['src'], m['dst']) for m in moves],
                         [('library/2025/06/A/IMG_1.JPG', '_duplicates/2025/06/B/IMG_1.JPG')])

    def test_applying_never_removes_a_file_it_only_moves_it(self):
        self.put('library/2025/06/A/IMG_1.JPG', 'same')
        self.put('library/2025/06/B/IMG_1.JPG', 'same')
        plan = self.plan()
        core.apply_moves(self.cfg, core.selected_moves(plan, self.cfg))
        self.assertEqual(len(self.tree()), 2)
        self.assertTrue(any(t.startswith('_duplicates/') for t in self.tree()))

    def test_a_half_is_left_alone_when_its_partner_is_kept(self):
        self.put('library/2025/06/A/IMG_1.HEIC', 'same still')
        self.put('library/2025/06/A/IMG_1.MOV', 'clip A')
        self.put('library/2025/06/B/IMG_1.HEIC', 'same still')
        self.put('library/2025/06/B/IMG_1.MOV', 'a different clip')
        plan = self.plan()
        moves, protected = core.duplicate_moves(self.cfg, plan)
        self.assertEqual(moves, [])
        self.assertEqual(len(protected), 1)

    def test_both_halves_marked_no_are_filed_together(self):
        for d in ('A', 'B'):
            self.put(f'library/2025/06/{d}/IMG_1.HEIC', 'same still')
            self.put(f'library/2025/06/{d}/IMG_1.MOV', 'same clip')
        plan = self.plan()
        self.assertEqual(len(plan['groups']), 2)
        moves = core.selected_moves(plan, self.cfg)
        self.assertEqual(len(moves), 2)
        self.assertEqual({Path(m['dst']).stem for m in moves}, {'IMG_1'})

    def test_a_group_can_be_left_alone(self):
        self.put('library/2025/06/A/IMG_1.JPG', 'same')
        self.put('library/2025/06/B/IMG_1.JPG', 'same')
        plan = self.plan()
        plan['excluded'] = [plan['groups'][0]['id']]
        self.assertEqual(core.selected_moves(plan, self.cfg), [])

    def test_unrelated_sidecars_that_happen_to_match_are_not_duplicates(self):
        self.put('library/2025/06/IMG_1.JPG.xmp', 'same')
        self.put('library/2025/06/IMG_2.JPG.xmp', 'same')
        self.assertEqual(self.plan()['groups'], [])


class DeletingDuplicates(Library):
    def plan(self, mode='delete'):
        plan = core.plan_duplicates(self.cfg)
        plan.update(excluded=[], excluded_kinds=[], mode=mode)
        return plan

    def test_deleting_removes_only_the_extra_copies_and_keeps_the_best_one(self):
        self.put('library/2025/06/Trip/IMG_1.JPG', 'same')
        self.put('library/2025/06/IMG_1.JPG', 'same')
        self.put('_duplicates/2025/06/IMG_1.JPG', 'same')
        self.put('library/2025/06/other.JPG', 'different')
        run = core.apply_moves(self.cfg, core.selected_moves(self.plan(), self.cfg))
        self.assertEqual(self.tree(), ['library/2025/06/Trip/IMG_1.JPG', 'library/2025/06/other.JPG'])
        self.assertEqual([m['status'] for m in run['moves']], ['deleted', 'deleted'])
        self.assertTrue(all(m['sha1'] and m['keep'] == 'library/2025/06/Trip/IMG_1.JPG' for m in run['moves']))

    def test_the_default_mode_still_only_files_them(self):
        self.put('library/2025/06/A/IMG_1.JPG', 'same')
        self.put('library/2025/06/B/IMG_1.JPG', 'same')
        core.apply_moves(self.cfg, core.selected_moves(self.plan('file'), self.cfg))
        self.assertEqual(len(self.tree()), 2)

    def test_nothing_is_deleted_if_the_kept_copy_changed_since_the_scan(self):
        keeper = self.put('library/2025/06/A/IMG_1.JPG', 'same')
        extra = self.put('library/2025/06/B/IMG_1.JPG', 'same')
        plan = self.plan()
        self.assertEqual(plan['groups'][0]['keep'], 'library/2025/06/A/IMG_1.JPG')
        keeper.write_text('edited since the scan')
        run = core.apply_moves(self.cfg, core.selected_moves(plan, self.cfg))
        self.assertEqual(run['moves'][0]['status'], 'skipped')
        self.assertTrue(extra.exists())

    def test_nothing_is_deleted_if_the_kept_copy_is_gone(self):
        keeper = self.put('library/2025/06/A/IMG_1.JPG', 'same')
        extra = self.put('library/2025/06/B/IMG_1.JPG', 'same')
        plan = self.plan()
        keeper.unlink()
        core.apply_moves(self.cfg, core.selected_moves(plan, self.cfg))
        self.assertTrue(extra.exists())

    def test_a_live_photo_half_is_never_deleted_while_its_partner_stays(self):
        self.put('library/2025/06/A/IMG_1.HEIC', 'same still')
        self.put('library/2025/06/A/IMG_1.MOV', 'clip A')
        self.put('library/2025/06/B/IMG_1.HEIC', 'same still')
        self.put('library/2025/06/B/IMG_1.MOV', 'a different clip')
        self.assertEqual(core.selected_moves(self.plan(), self.cfg), [])

    def test_undo_says_what_cannot_be_put_back(self):
        self.put('library/2025/06/A/IMG_1.JPG', 'same')
        self.put('library/2025/06/B/IMG_1.JPG', 'same')
        run = core.apply_moves(self.cfg, core.selected_moves(self.plan(), self.cfg))
        result = core.undo_run(self.cfg, run)
        self.assertEqual((result['restored'], result['not_restorable']), (0, 1))
        self.assertEqual(len(self.tree()), 1)

    def test_the_api_wants_the_word_DELETE_and_will_not_delete_without_it(self):
        self.put('library/2025/06/A/IMG_1.JPG', 'same')
        self.put('library/2025/06/B/IMG_1.JPG', 'same')
        app = server.App(self.cfg)
        app.route('POST', '/api/plans', {}, {'kind': 'duplicates'})
        for _ in range(200):
            job = app.jobs.status()
            if job['state'] != 'running':
                break
            time.sleep(0.02)
        pid = job['result']['plan']
        self.assertEqual(app.route('PATCH', f'/api/plans/{pid}', {}, {'mode': 'nonsense'})[0], 400)
        app.route('PATCH', f'/api/plans/{pid}', {}, {'mode': 'delete'})
        self.assertEqual(app.route('GET', f'/api/plans/{pid}', {}, {})[1]['mode'], 'delete')
        self.assertEqual(app.route('POST', f'/api/plans/{pid}/apply', {}, {})[0], 400)
        self.assertEqual(app.route('POST', f'/api/plans/{pid}/apply', {}, {'confirm': 'delete'})[0], 400)
        self.assertEqual(len(self.tree()), 2)
        self.assertEqual(app.route('POST', f'/api/plans/{pid}/apply', {}, {'confirm': 'DELETE'})[0], 202)
        for _ in range(200):
            if app.jobs.status()['state'] != 'running':
                break
            time.sleep(0.02)
        self.assertEqual(len(self.tree()), 1)


class ImmichBase(Library):
    PREFIX = '/mnt/mahir-personal/'

    def asset(self, id_, rel, content='', **extra):
        return {'id': id_, 'originalPath': self.PREFIX + rel, 'originalFileName': os.path.basename(rel), 'isTrashed': True,
                'type': 'IMAGE', 'checksum': sha1b64(content), **extra}

    def connect(self, assets, **kw):
        self.fake = FakeImmich(assets, **kw)
        self.addCleanup(self.fake.stop)
        return immich.Immich(self.fake.url, 'k3y')

    def plan(self, assets, mode='file', **kw):
        plan = core.plan_immich(self.cfg, self.connect(assets, **kw))
        plan.update(excluded=[], excluded_kinds=[], mode=mode)
        return plan


class ImmichTrash(ImmichBase):
    def test_each_trashed_asset_is_found_in_the_library_or_reported_missing_or_outside(self):
        self.put('library/2025/06/a.jpg', 'A')
        plan = self.plan([self.asset('1', 'library/2025/06/a.jpg', 'A'),
                          self.asset('2', 'library/2025/06/gone.jpg', 'x'),
                          {**self.asset('3', 'x'), 'originalPath': '/data/upload/abc/def.jpg'}])
        by = {i['id']: i for i in plan['items']}
        self.assertEqual((by['1']['status'], by['1']['rel'], by['1']['size']), ('file', 'library/2025/06/a.jpg', 1))
        self.assertEqual((by['2']['status'], by['3']['status']), ('missing', 'outside'))
        self.assertEqual(plan['stats']['kinds'], {'file': 1, 'missing': 1, 'outside': 1})

    def test_only_assets_immich_says_are_trashed_are_listed(self):
        self.put('library/2025/06/a.jpg', 'A')
        self.put('library/2025/06/b.jpg', 'B')
        plan = self.plan([self.asset('1', 'library/2025/06/a.jpg', 'A'),
                          self.asset('2', 'library/2025/06/b.jpg', 'B', isTrashed=False)])
        self.assertEqual([i['id'] for i in plan['items']], ['1'])

    def test_an_older_immich_that_rejects_the_current_search_is_still_read(self):
        self.put('library/2025/06/a.jpg', 'A')
        plan = self.plan([self.asset('1', 'library/2025/06/a.jpg', 'A')], legacy=True)
        self.assertEqual(len(plan['items']), 1)
        bodies = [c[2] for c in self.fake.calls if c[1] == '/api/search/metadata']
        self.assertIn('filter', bodies[0])
        self.assertTrue(bodies[-1]['withDeleted'])

    def test_every_page_of_the_trash_is_read_and_the_key_is_sent(self):
        self.fake = FakeImmich([self.asset(str(i), f'library/2025/06/p{i}.jpg') for i in range(7)])
        self.addCleanup(self.fake.stop)
        client = immich.Immich(self.fake.url, 'k3y')
        old, immich.PAGE = immich.PAGE, 3
        try:
            self.assertEqual(len(client.trashed()), 7)
        finally:
            immich.PAGE = old
        self.assertTrue(all(c[3] == 'k3y' for c in self.fake.calls))

    def test_a_wrong_key_is_a_clear_error_not_an_empty_trash(self):
        self.fake = FakeImmich([], key='right')
        self.addCleanup(self.fake.stop)
        with self.assertRaises(immich.ImmichError) as ctx:
            immich.Immich(self.fake.url, 'wrong').trashed()
        self.assertIn('401', str(ctx.exception))

    def test_a_live_photo_clip_comes_with_its_still_whichever_way_it_is_linked(self):
        self.put('library/2025/06/IMG_1.HEIC', 'still1')
        self.put('library/2025/06/IMG_1.MOV', 'clip1')
        self.put('library/2025/06/IMG_2.HEIC', 'still2')
        self.put('library/2025/06/IMG_2.MOV', 'clip2')
        plan = self.plan([
            self.asset('s1', 'library/2025/06/IMG_1.HEIC', 'still1', livePhotoVideoId='c1'),
            self.asset('c1', 'library/2025/06/IMG_1.MOV', 'clip1', type='VIDEO'),     # linked by Immich
            self.asset('s2', 'library/2025/06/IMG_2.HEIC', 'still2')])                  # found by name
        self.assertEqual([i['id'] for i in plan['items']], ['s1', 's2'])
        self.assertEqual([i['clip']['rel'] for i in plan['items']], ['library/2025/06/IMG_1.MOV', 'library/2025/06/IMG_2.MOV'])
        self.assertEqual(plan['stats']['live'], 2)

    def test_removing_files_moves_them_aside_and_undo_puts_them_back(self):
        self.put('library/2025/06/IMG_1.HEIC', 'still1')
        self.put('library/2025/06/IMG_1.MOV', 'clip1')
        before = self.tree()
        plan = self.plan([self.asset('s1', 'library/2025/06/IMG_1.HEIC', 'still1', livePhotoVideoId='c1'),
                          self.asset('c1', 'library/2025/06/IMG_1.MOV', 'clip1', type='VIDEO')])
        run = core.apply_moves(self.cfg, core.selected_moves(plan, self.cfg))
        self.assertEqual(self.tree(), ['_removed/library/2025/06/IMG_1.HEIC', '_removed/library/2025/06/IMG_1.MOV'])
        self.assertEqual(core.undo_run(self.cfg, run)['restored'], 2)
        self.assertEqual(self.tree(), before)

    def test_deleting_removes_the_still_and_its_clip_for_good(self):
        self.put('library/2025/06/IMG_1.HEIC', 'still1')
        self.put('library/2025/06/IMG_1.MOV', 'clip1')
        plan = self.plan([self.asset('s1', 'library/2025/06/IMG_1.HEIC', 'still1', livePhotoVideoId='c1'),
                          self.asset('c1', 'library/2025/06/IMG_1.MOV', 'clip1', type='VIDEO')], mode='delete')
        run = core.apply_moves(self.cfg, core.selected_moves(plan, self.cfg))
        self.assertEqual(self.tree(), [])
        self.assertEqual(sorted(m['status'] for m in run['moves']), ['deleted', 'deleted'])
        self.assertEqual(core.undo_run(self.cfg, run)['not_restorable'], 2)

    def test_a_file_that_is_no_longer_the_one_immich_trashed_is_not_deleted(self):
        path = self.put('library/2025/06/a.jpg', 'what immich trashed')
        plan = self.plan([self.asset('1', 'library/2025/06/a.jpg', 'what immich trashed')], mode='delete')
        path.write_text('a different photo now at the same path')
        run = core.apply_moves(self.cfg, core.selected_moves(plan, self.cfg))
        self.assertEqual(run['moves'][0]['status'], 'skipped')
        self.assertTrue(path.exists())

    def test_a_symlink_is_never_followed_or_deleted(self):
        target = self.put('elsewhere/real.jpg', 'precious')
        link = self.root / 'library/2025/06/a.jpg'
        link.parent.mkdir(parents=True)
        link.symlink_to(target)
        plan = self.plan([self.asset('1', 'library/2025/06/a.jpg', 'precious')], mode='delete')
        self.assertEqual(plan['items'][0]['status'], 'symlink')
        self.assertEqual(core.selected_moves(plan, self.cfg), [])
        self.assertTrue(target.exists())

    def test_a_file_swapped_for_a_symlink_after_the_scan_is_not_deleted(self):
        path = self.put('library/2025/06/a.jpg', 'same bytes')
        target = self.put('elsewhere/real.jpg', 'same bytes')       # identical content: only the link check can stop this
        plan = self.plan([self.asset('1', 'library/2025/06/a.jpg', 'same bytes')], mode='delete')
        path.unlink()
        path.symlink_to(target)
        run = core.apply_moves(self.cfg, core.selected_moves(plan, self.cfg))
        self.assertEqual(run['moves'][0]['status'], 'skipped')
        self.assertTrue(path.is_symlink() and target.exists())

    def test_a_path_that_climbs_out_of_the_media_folder_is_refused(self):
        plan = self.plan([self.asset('1', '../../etc/passwd', 'x')])
        self.assertEqual(plan['items'][0]['status'], 'outside')
        self.assertEqual(core.selected_moves(plan, self.cfg), [])

    def test_unticked_items_are_left_alone(self):
        self.put('library/2025/06/a.jpg', 'A')
        self.put('library/2025/06/b.jpg', 'B')
        plan = self.plan([self.asset('1', 'library/2025/06/a.jpg', 'A'), self.asset('2', 'library/2025/06/b.jpg', 'B')])
        plan['excluded'] = ['immich:2']
        core.apply_moves(self.cfg, core.selected_moves(plan, self.cfg))
        self.assertEqual(self.tree(), ['_removed/library/2025/06/a.jpg', 'library/2025/06/b.jpg'])


class ImmichApi(ImmichBase):
    def setUp(self):
        super().setUp()
        self.put('library/2025/06/a.jpg', 'A')
        self.put('library/2025/06/b.jpg', 'B')
        self.client = self.connect([self.asset('1', 'library/2025/06/a.jpg', 'A'), self.asset('2', 'library/2025/06/b.jpg', 'B'),
                                    self.asset('3', 'library/2025/06/gone.jpg', 'x')])
        self.app = server.App(self.cfg, immich=self.client)

    def run_job(self, body):
        self.app.route('POST', '/api/plans', {}, body)
        for _ in range(300):
            job = self.app.jobs.status()
            if job['state'] != 'running':
                return job
            time.sleep(0.02)
        self.fail('job did not finish')

    def test_the_connection_is_reported_and_a_missing_key_is_not_an_error(self):
        self.assertEqual(self.app.route('GET', '/api/immich', {}, {})[1],
                         {'configured': True, 'connected': True, 'user': 'me@example.com', 'version': 'v3.4.1'})
        self.assertEqual(server.App(self.cfg).route('GET', '/api/immich', {}, {})[1], {'configured': False})
        bad = server.App(self.cfg, immich=immich.Immich(self.fake.url, 'wrong'))
        self.assertFalse(bad.route('GET', '/api/immich', {}, {})[1]['connected'])

    def test_a_key_without_user_read_still_connects(self):
        self.fake.forbidden = {'/api/users/me'}
        info = self.app.route('GET', '/api/immich', {}, {})[1]
        self.assertTrue(info['connected'])
        self.assertEqual(info['user'], '')

    def test_without_immich_a_trash_plan_is_refused_clearly(self):
        with self.assertRaises(ValueError):
            server.App(self.cfg).route('POST', '/api/plans', {}, {'kind': 'immich'})

    def test_review_filter_bulk_untick_and_apply(self):
        job = self.run_job({'kind': 'immich'})
        self.assertEqual(job['state'], 'done', job)
        pid = job['result']['plan']
        _, plan = self.app.route('GET', f'/api/plans/{pid}', {}, {})
        self.assertEqual((plan['items'], plan['selected_items']), (3, 2))
        _, page = self.app.route('GET', f'/api/plans/{pid}/items', {'status': ['missing']}, {})
        self.assertEqual([i['id'] for i in page['items']], ['3'])
        _, page = self.app.route('GET', f'/api/plans/{pid}/items', {'q': ['b.jpg']}, {})
        self.assertEqual([i['id'] for i in page['items']], ['2'])
        self.app.route('PATCH', f'/api/plans/{pid}', {}, {'filter': {'q': 'b.jpg'}, 'selected': False})
        self.assertEqual(self.app.route('GET', f'/api/plans/{pid}', {}, {})[1]['selected_items'], 1)
        self.app.route('PATCH', f'/api/plans/{pid}', {}, {'mode': 'delete'})
        self.assertEqual(self.app.route('POST', f'/api/plans/{pid}/apply', {}, {})[0], 400)   # needs DELETE
        self.assertEqual(self.app.route('POST', f'/api/plans/{pid}/apply', {}, {'confirm': 'DELETE'})[0], 202)
        for _ in range(300):
            if self.app.jobs.status()['state'] != 'running':
                break
            time.sleep(0.02)
        self.assertEqual(self.tree(), ['library/2025/06/b.jpg'])


class BulkDuplicateChoices(Library):
    def setUp(self):
        super().setUp()
        for month in ('05', '06', '07'):    # three groups, each a copy in Trip/ and a copy in Backup/
            self.put(f'library/2025/{month}/Trip/IMG_{month}.JPG', f'photo {month}')
            self.put(f'library/2025/{month}/Backup/IMG_{month}.JPG', f'photo {month}')
        self.put('library/2025/08/Solo/IMG_8.JPG', 'eight')
        self.put('library/2025/08/Other/IMG_8.JPG', 'eight')
        self.app = server.App(self.cfg)
        self.app.route('POST', '/api/plans', {}, {'kind': 'duplicates'})
        for _ in range(300):
            job = self.app.jobs.status()
            if job['state'] != 'running':
                break
            time.sleep(0.02)
        self.pid = job['result']['plan']

    def patch(self, body):
        return self.app.route('PATCH', f'/api/plans/{self.pid}', {}, body)

    def plan(self):
        return self.app.jobs.plan(self.pid)

    def keeps(self):
        return sorted(g['keep'] for g in self.plan()['groups'])

    def test_keep_the_copy_in_a_folder_moves_the_keeper_in_every_group_that_has_one(self):
        self.patch({'keep_reset': {}})
        august_before = [k for k in self.keeps() if '/2025/08/' in k]
        status, res = self.patch({'keep_where': {'contains': '/Backup/'}})
        self.assertEqual((status, res['changed']), (200, 3))
        keeps = self.keeps()
        self.assertEqual([k for k in keeps if '/Backup/' in k], [f'library/2025/0{m}/Backup/IMG_0{m}.JPG' for m in (5, 6, 7)])
        # the August group has no Backup copy: left exactly as it was
        self.assertEqual([k for k in keeps if '/2025/08/' in k], august_before)

    def test_it_only_touches_the_groups_the_search_is_showing(self):
        self.patch({'keep_reset': {}})
        self.patch({'keep_where': {'contains': '/Backup/', 'q': '2025/06'}})
        backups = [k for k in self.keeps() if '/Backup/' in k]
        self.assertEqual(backups, ['library/2025/06/Backup/IMG_06.JPG'])

    def test_reset_puts_the_default_best_copy_back(self):
        default = self.keeps()
        self.patch({'keep_where': {'contains': '/Backup/'}})
        self.assertNotEqual(self.keeps(), default)
        self.patch({'keep_reset': {}})
        self.assertEqual(self.keeps(), default)

    def test_a_keep_rule_with_no_folder_is_refused(self):
        self.assertEqual(self.patch({'keep_where': {'contains': '  '}})[0], 400)

    def test_ticking_groups_in_bulk_follows_the_search(self):
        self.patch({'filter': {'q': '2025/0'}, 'selected': False})       # the 05, 06, 07 and 08 groups: all of them
        self.assertEqual(len(self.plan()['excluded']), 4)
        self.patch({'filter': {'q': '2025/06'}, 'selected': True})
        self.assertEqual(len(self.plan()['excluded']), 3)
        _, page = self.app.route('GET', f'/api/plans/{self.pid}/groups', {'q': ['2025/0']}, {})
        self.assertEqual((page['total'], page['selected']), (4, 1))

    def test_the_moves_follow_the_chosen_keepers(self):
        self.patch({'keep_where': {'contains': '/Backup/'}})
        moves = core.selected_moves(self.plan(), self.cfg)
        removed = {m['src'] for m in moves}
        self.assertNotIn('library/2025/06/Backup/IMG_06.JPG', removed)    # the one chosen to keep is not touched
        self.assertIn('library/2025/06/Trip/IMG_06.JPG', removed)         # the other copy is the extra


class Previews(Library):
    """Seeing a photo before anything happens to it."""

    def fake_vips(self):
        """A vipsthumbnail that writes a small JPEG-looking file and records how it was called."""
        tool = self.bin / 'vipsthumbnail'
        tool.write_text('#!/bin/sh\necho "$@" >> "$VIPS_LOG"\n'
                        'for a in "$@"; do case "$a" in *.part.jpg*) out="${a%%[*}";; esac; done\n'
                        'printf "\\377\\330fake-thumb" > "$out"\n')
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
        os.environ['VIPS_LOG'] = str(self.tmp / 'vips.log')

    def test_a_heic_is_thumbnailed_once_and_then_served_from_the_cache(self):
        self.fake_vips()
        self.put('library/2025/06/IMG_1[2].HEIC', 'heic bytes')   # a bracket in the name must not reach vips
        first = previews.thumbnail(self.cfg, 'library/2025/06/IMG_1[2].HEIC', 300)
        self.assertTrue(first.startswith(str(self.state / 'thumbs')))
        self.assertEqual(Path(first).read_bytes()[:2], b'\xff\xd8')
        self.assertEqual(previews.thumbnail(self.cfg, 'library/2025/06/IMG_1[2].HEIC', 300), first)
        log = (self.tmp / 'vips.log').read_text().splitlines()
        self.assertEqual(len(log), 1)
        self.assertIn('640x640', log[0])                  # 300 rounds up to a size that is made
        self.assertNotIn('[2]', log[0].split(' -o ')[0])

    def test_a_changed_file_gets_a_fresh_thumbnail(self):
        self.fake_vips()
        p = self.put('a.heic', 'one')
        old = previews.thumbnail(self.cfg, 'a.heic')
        p.write_bytes(b'something else entirely')
        self.assertNotEqual(previews.thumbnail(self.cfg, 'a.heic'), old)

    def test_without_libvips_a_jpeg_is_served_as_it_is_and_a_heic_has_no_preview(self):
        self.put('a.jpg', 'jpeg')
        self.put('b.heic', 'heic')
        self.assertEqual(previews.thumbnail(self.cfg, 'a.jpg'), str(self.root / 'a.jpg'))
        with self.assertRaises(previews.NoPreview):
            previews.thumbnail(self.cfg, 'b.heic')

    def test_videos_and_other_files_and_paths_outside_the_media_folder_are_refused(self):
        self.put('clip.mov', 'v')
        self.put('notes.txt', 't')
        for rel in ('clip.mov', 'notes.txt'):
            with self.assertRaises(previews.NoPreview):
                previews.thumbnail(self.cfg, rel)
        with self.assertRaises(ValueError):
            previews.thumbnail(self.cfg, '../outside.jpg')
        with self.assertRaises(FileNotFoundError):
            previews.thumbnail(self.cfg, 'missing.jpg')

    def test_a_folder_is_shown_by_its_first_photo_not_a_video(self):
        self.put('library/2025/06/Trip/a_clip.mov', 'v')
        self.put('library/2025/06/Trip/b_photo.jpg', 'jpeg')
        self.put('library/2025/06/Only_video/c.mov', 'v')
        self.assertEqual(previews.cover(self.cfg, 'library/2025/06/Trip'), 'library/2025/06/Trip/b_photo.jpg')
        self.assertEqual(previews.thumbnail(self.cfg, 'library/2025/06/Trip'), str(self.root / 'library/2025/06/Trip/b_photo.jpg'))
        with self.assertRaises(previews.NoPreview):
            previews.thumbnail(self.cfg, 'library/2025/06/Only_video')

    def test_identical_and_different_files_are_told_apart_by_content(self):
        self.put('a.jpg', 'same bytes')
        self.put('b.jpg', 'same bytes')
        self.put('c.jpg', 'same size!')
        self.put('d.jpg', 'longer than the others')
        self.assertTrue(previews.same_bytes(self.cfg, 'a.jpg', 'b.jpg'))
        self.assertFalse(previews.same_bytes(self.cfg, 'a.jpg', 'c.jpg'))
        self.assertFalse(previews.same_bytes(self.cfg, 'a.jpg', 'd.jpg'))

    def test_facts_report_size_and_what_exiftool_knows(self):
        self.put('a.jpg', 'twelve bytes', '2025-06')
        self.sync_dates()
        f = previews.facts(self.cfg, 'a.jpg')
        self.assertEqual((f['size'], f['width'], f['camera'], f['taken'], f['video']), (12, 160, 'Demo camera', '2025-06', False))


class NoDate(Library):
    def setUp(self):
        super().setUp()
        self.app = server.App(self.cfg)

    def wait(self):
        for _ in range(200):
            job = self.app.jobs.status()
            if job['state'] != 'running':
                return job
            time.sleep(0.02)
        self.fail('the job never finished')

    def test_a_date_in_the_file_name_is_offered_but_a_long_id_is_not(self):
        self.assertEqual(nodate.hint('IMG_20230614_101010.jpg'), '2023-06-14')
        self.assertEqual(nodate.hint('Screenshot 2022-11-03 at 9.41.png'), '2022-11-03')
        self.assertEqual(nodate.hint('176971082174389512.JPG'), '')
        self.assertEqual(nodate.hint('IMG_20231345.jpg'), '')       # month 13
        self.assertEqual(nodate.hint('IMG_20230230.jpg'), '')       # no 30th of February

    def test_the_set_aside_media_is_listed_with_hints_and_other_files_are_not(self):
        self.put('_no_date/_inbox/loose/IMG_20230614.jpg', 'a')
        self.put('_no_date/_inbox/loose/Scans/s1.jpg', 'bb')
        self.put('_no_date/_inbox/loose/notes.txt', 'not media')
        self.put('library/2025/06/dated.jpg', 'c', '2025-06')
        found = {f['name']: f for f in nodate.files(self.cfg)}
        self.assertEqual(sorted(found), ['IMG_20230614.jpg', 's1.jpg'])
        self.assertEqual((found['IMG_20230614.jpg']['hint'], found['s1.jpg']['size']), ('2023-06-14', 2))

    def test_the_date_is_validated_before_anything_is_written(self):
        self.assertEqual(nodate.stamp('2023-06-14', '09:30'), '2023:06:14 09:30:00')
        self.assertEqual(nodate.stamp('2023-06-14', ''), '2023:06:14 12:00:00')
        for bad in (('14/06/2023', '12:00'), ('2023-02-30', '12:00'), ('1950-01-01', '12:00'), ('2023-06-14', '25:00')):
            with self.assertRaises(ValueError):
                nodate.stamp(*bad)

    def test_dating_writes_the_date_then_sends_the_photo_to_the_inbox_where_it_sorts_by_it(self):
        self.put('_no_date/_inbox/loose/a.jpg', 'A')
        self.put('_no_date/_inbox/loose/Scans/b.jpg', 'B')
        self.put('_inbox/loose/b.jpg', 'already here')     # a name clash in the inbox
        self.sync_dates()
        self.app.jobs.start_set_dates(['_no_date/_inbox/loose/a.jpg', '_no_date/_inbox/loose/Scans/b.jpg'], '2023-06-14', '10:00')
        job = self.wait()
        self.assertEqual(job['state'], 'done', job)
        self.assertEqual(job['result']['failed'], [])
        self.assertEqual(self.tree(), ['_inbox/loose/a.jpg', '_inbox/loose/b.jpg', '_inbox/loose/b_1.jpg'])
        written = json.loads((self.tmp / 'dates.json').read_text())
        self.assertEqual(written['_no_date/_inbox/loose/a.jpg'], '2023:06:14 10:00:00')       # the whole moment, as ExifTool stores it
        # the stand-in keeps dates by path, a real file carries its date along: follow the moves
        self.dates.update({'_inbox/loose/a.jpg': written['_no_date/_inbox/loose/a.jpg'],
                           '_inbox/loose/b_1.jpg': written['_no_date/_inbox/loose/Scans/b.jpg']})
        # the next inbox sort files them by the date that was written
        plan, _ = self.sort()
        self.assertEqual(sorted(m['dst'] for m in plan['moves'] if m['src'].endswith(('a.jpg', 'b_1.jpg'))),
                         ['library/2023/06/a.jpg', 'library/2023/06/b_1.jpg'])
        # and the run is in History, with the moves undoable
        run = self.app.jobs.runs()[-1]
        self.assertEqual((run['kind'], run['counts']['moved']), ('set-date', 2))

    def test_a_file_that_cannot_hold_a_date_stays_put_and_is_reported(self):
        self.put('_no_date/_inbox/loose/ok.jpg', 'A')
        self.put('_no_date/_inbox/loose/anim.gif', 'G')
        self.sync_dates()
        os.environ['FAKE_CANNOT_WRITE'] = '.gif'
        self.app.jobs.start_set_dates(['_no_date/_inbox/loose/ok.jpg', '_no_date/_inbox/loose/anim.gif'], '2023-06-14')
        job = self.wait()
        self.assertEqual(job['state'], 'done', job)
        self.assertEqual([f['src'] for f in job['result']['failed']], ['_no_date/_inbox/loose/anim.gif'])
        self.assertIn('cannot hold a date', job['result']['failed'][0]['note'])
        self.assertEqual(self.tree(), ['_inbox/loose/ok.jpg', '_no_date/_inbox/loose/anim.gif'])

    def test_only_files_set_aside_for_having_no_date_can_be_dated(self):
        self.put('library/2025/06/dated.jpg', 'x', '2025-06')
        self.put('_inbox/loose/new.jpg', 'y')
        for rel in ('library/2025/06/dated.jpg', '_inbox/loose/new.jpg', '../etc/passwd'):
            with self.assertRaises(ValueError):
                self.app.jobs.start_set_dates([rel], '2023-06-14')
        with self.assertRaises(ValueError):
            self.app.jobs.start_set_dates([], '2023-06-14')
        self.assertIsNone(self.app.jobs.status())     # nothing was started


class PreviewRoutes(Library):
    """The picture routes, over real HTTP: they return bytes, honour Range, and stay in the media folder."""

    def setUp(self):
        super().setUp()
        import http.client
        from http.server import ThreadingHTTPServer
        self.put('a.jpg', 'JPEGBYTES')
        self.put('clip.mov', '0123456789')
        self.put('notes.txt', 'secret')
        self.srv = ThreadingHTTPServer(('127.0.0.1', 0), server.handler(server.App(self.cfg)))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.http = http.client

    def tearDown(self):
        self.srv.shutdown()
        super().tearDown()

    def get(self, path, headers=None):
        c = self.http.HTTPConnection('127.0.0.1', self.srv.server_port)
        c.request('GET', path, headers=headers or {})
        r = c.getresponse()
        return r.status, dict(r.getheaders()), r.read()

    def test_a_preview_is_an_image_that_the_browser_may_cache(self):
        status, headers, body = self.get('/api/preview?path=a.jpg&w=240')
        self.assertEqual((status, body), (200, b'JPEGBYTES'))
        self.assertTrue(headers['Content-Type'].startswith('image/jpeg'))
        self.assertIn('max-age', headers['Cache-Control'])

    def test_a_video_can_be_read_in_ranges_so_it_can_seek(self):
        status, headers, body = self.get('/api/file?path=clip.mov', {'Range': 'bytes=2-5'})
        self.assertEqual((status, body, headers['Content-Range']), (206, b'2345', 'bytes 2-5/10'))
        self.assertEqual(self.get('/api/file?path=clip.mov', {'Range': 'bytes=-3'})[2], b'789')
        self.assertEqual(self.get('/api/file?path=clip.mov', {'Range': 'bytes=4-'})[2], b'456789')
        self.assertEqual(self.get('/api/file?path=clip.mov', {'Range': 'bytes=50-'})[0], 416)
        self.assertEqual(self.get('/api/file?path=clip.mov')[2], b'0123456789')

    def test_a_folder_can_be_previewed_but_never_downloaded(self):
        self.put('Trip/b.jpg', 'FOLDERCOVER')
        self.assertEqual(self.get('/api/preview?path=Trip&w=240')[2], b'FOLDERCOVER')
        self.assertEqual(self.get('/api/file?path=Trip')[0], 400)
        self.assertEqual(self.get('/api/preview?path=..')[0], 400)       # not out of the media folder either

    def test_nothing_outside_the_media_or_that_is_not_a_photo_is_served(self):
        self.assertEqual(self.get('/api/file?path=notes.txt')[0], 400)
        self.assertEqual(self.get('/api/file?path=../state/plans')[0], 400)
        self.assertEqual(self.get('/api/file?path=..%2f..%2fetc%2fpasswd.jpg')[0], 400)
        self.assertEqual(self.get('/api/preview?path=missing.jpg')[0], 404)
        self.assertEqual(self.get('/api/preview?path=clip.mov')[0], 404)      # a video has no thumbnail
        self.assertEqual(self.get('/api/info?path=notes.txt')[0], 400)
        self.assertEqual(self.get('/api/same?a=a.jpg&b=notes.txt')[0], 400)


class ActivityLog(Library):
    """What the service did, kept on disk: so a restart, a stop or a failure leaves a trace."""

    def setUp(self):
        super().setUp()
        self.app = server.App(self.cfg)

    def wait(self, app=None):
        app = app or self.app
        for _ in range(300):
            job = app.jobs.status()
            if job['state'] != 'running':
                return job
            time.sleep(0.02)
        self.fail('the job never finished')

    def test_a_finished_scan_is_logged_with_what_it_found_and_that_it_is_not_applied(self):
        self.put('_inbox/loose/a.jpg', 'A', '2025-06')
        self.sync_dates()
        self.app.jobs.start_plan('sort')
        self.wait()
        row = self.app.jobs.activity()[0]
        self.assertEqual((row['kind'], row['state'], row['stats']['moves'], row['applied']), ('plan-sort', 'done', 1, None))
        self.assertTrue(row['finished'] >= row['started'])
        # it survives a restart: a new service reads the same log
        again = server.App(self.cfg)
        self.assertEqual(again.jobs.activity()[0]['id'], row['id'])

    def test_a_job_that_a_restart_cut_short_is_logged_as_interrupted(self):
        gate = threading.Event()
        self.app.jobs.start('plan-duplicates', lambda progress: gate.wait(5))
        restarted = server.App(self.cfg)       # the old service is gone, the new one starts up
        row = restarted.jobs.activity()[0]
        self.assertEqual(row['state'], 'interrupted')
        self.assertIn('restarted', row['error'])
        gate.set()
        self.wait()           # the old service's thread ends before the folder is removed

    def test_a_failing_job_is_logged_with_its_error(self):
        def boom(progress):
            raise RuntimeError('disk on fire')
        self.app.jobs.start('plan-sort', boom)
        self.wait()
        row = self.app.jobs.activity()[0]
        self.assertEqual(row['state'], 'error')
        self.assertIn('disk on fire', row['error'])

    def test_a_scan_can_be_stopped_but_an_apply_cannot(self):
        gate = threading.Event()

        def scan(progress):
            gate.wait(5)
            progress(1, 2, 'next')          # the stop is noticed the next time it reports
        self.app.jobs.start('plan-duplicates', scan)
        self.assertEqual(self.app.route('POST', '/api/job/cancel', {}, {})[0], 200)
        gate.set()
        self.assertEqual(self.wait()['state'], 'cancelled')
        self.app.jobs.start('apply', lambda progress: gate.wait(0.3))
        with self.assertRaises(ValueError):
            self.app.jobs.cancel()
        self.wait()
        with self.assertRaises(ValueError):
            self.app.jobs.cancel()          # nothing is running now

    def test_the_duplicates_found_so_far_are_saved_while_the_scan_runs(self):
        for i in range(3):
            self.put(f'library/2025/06/a{i}.jpg', f'identical-{i}')
            self.put(f'library/2025/07/b{i}.jpg', f'identical-{i}')
        seen = []
        real = core.plan_duplicates

        def spy(cfg, progress=core._noop, checkpoint=None):
            # ask for a checkpoint after every size bucket, and look at the plan the page would load
            def look(plan):
                job = self.app.jobs.status()
                checkpoint(plan)
                seen.append((self.app.jobs.plan(job['plan'])['partial'], self.app.jobs.plan(job['plan'])['stats']['groups']))
            return real(cfg, progress, look)
        orig_time = time.time
        try:
            core.plan_duplicates = spy
            core.time = type('T', (), {'time': staticmethod(lambda c=iter(range(0, 10000, 10)): next(c))})
            self.app.jobs.start_plan('duplicates')
            job = self.wait()
        finally:
            core.plan_duplicates = real
            core.time = time
        self.assertEqual(job['state'], 'done', job)
        self.assertTrue(seen and all(partial for partial, _ in seen))
        final = self.app.jobs.plan(job['result']['plan'])
        self.assertFalse(final['partial'])
        self.assertEqual(final['stats']['groups'], 3)
        self.assertEqual(self.app.jobs.activity()[0]['stats']['groups'], 3)

    def test_a_new_scan_replaces_the_earlier_unapplied_one_of_its_kind_only(self):
        self.put('_inbox/loose/a.jpg', 'A', '2025-06')
        self.sync_dates()
        ids = []
        for kind in ('sort', 'sort', 'duplicates'):
            self.app.jobs.start_plan(kind)
            ids.append(self.wait()['result']['plan'])
        kept = {p['id'] for p in self.app.jobs.plans()}
        self.assertEqual(kept, {ids[1], ids[2]})               # the first sort scan was replaced, the duplicates scan is its own kind
        applied = self.app.jobs.plan(ids[1])
        applied['applied'] = 'run1'
        self.app.jobs.save_plan(applied)
        self.app.jobs.start_plan('sort')
        newest = self.wait()['result']['plan']
        self.assertEqual({p['id'] for p in self.app.jobs.plans()}, {ids[1], ids[2], newest})   # an applied plan is history, kept

    def test_choices_are_refused_while_their_scan_is_still_running(self):
        gate = threading.Event()
        plan = {'id': 'p1', 'kind': 'duplicates', 'groups': [], 'moves': [], 'excluded': [], 'excluded_kinds': [], 'applied': None}
        self.app.jobs.save_plan(plan)
        self.app.jobs.start('plan-duplicates', lambda progress: gate.wait(5), plan='p1')
        self.assertEqual(self.app.route('PATCH', '/api/plans/p1', {}, {'all': True})[0], 409)
        gate.set()
        self.wait()
        self.assertEqual(self.app.route('PATCH', '/api/plans/p1', {}, {'all': True})[0], 200)


class Restarts(Library):
    """A deploy replaces the service. Scans must come through it: nothing is read twice, and the cut-short scan runs again by itself."""

    def counting_digest(self):
        calls = []
        real = core._digest
        core._digest = lambda path, limit=None: (calls.append((os.path.basename(path), limit)), real(path, limit))[1]
        self.addCleanup(setattr, core, '_digest', real)
        return calls

    def library(self):
        for i in range(4):
            self.put(f'library/2025/06/a{i}.jpg', f'identical-{i}')
            self.put(f'library/2025/07/b{i}.jpg', f'identical-{i}')
        self.put('library/2025/08/lone.jpg', 'x' * 11)

    def test_a_second_scan_reads_no_file_again(self):
        self.library()
        calls = self.counting_digest()
        first = core.plan_duplicates(self.cfg)
        read = len(calls)
        self.assertTrue(read >= 16)       # every candidate was read the first time
        again = core.plan_duplicates(self.cfg)
        self.assertEqual(len(calls), read)   # and not once more
        self.assertEqual(again['groups'], first['groups'])

    def test_a_changed_file_is_read_again_and_judged_by_what_it_is_now(self):
        self.library()
        core.plan_duplicates(self.cfg)
        calls = self.counting_digest()
        p = self.root / 'library/2025/07/b0.jpg'
        p.write_bytes(b'something-else')       # no longer a copy of a0
        os.utime(p, (1, 1))
        plan = core.plan_duplicates(self.cfg)
        self.assertEqual(sorted(n for n, _ in calls), [])            # a different size: not even a candidate
        self.assertEqual(plan['stats']['groups'], 3)
        p.write_bytes(b'identical-0')          # a copy again, same size as before
        os.utime(p, (2, 2))
        calls.clear()
        self.assertEqual(core.plan_duplicates(self.cfg)['stats']['groups'], 4)
        self.assertIn('b0.jpg', [n for n, _ in calls])           # re-read, because its time changed

    def test_deleting_always_reads_the_bytes_and_ignores_the_cache(self):
        self.put('library/2025/06/keep.jpg', 'same bytes')
        self.put('library/2025/07/extra.jpg', 'same bytes')
        core.plan_duplicates(self.cfg)                            # both are now cached as identical
        extra = self.root / 'library/2025/07/extra.jpg'
        st = extra.stat()
        extra.write_bytes(b'DIFFERENT!!')                          # same size, mtime put back: a cache would be fooled
        os.utime(extra, ns=(st.st_atime_ns, st.st_mtime_ns))
        entry = core.delete_copy(self.cfg, {'src': 'library/2025/07/extra.jpg', 'keep': 'library/2025/06/keep.jpg'})
        self.assertEqual(entry['status'], 'skipped')
        self.assertTrue(extra.exists())

    def test_a_scan_cut_short_by_a_restart_runs_again_on_its_own_and_reuses_what_it_read(self):
        self.library()
        old = server.App(self.cfg)
        calls = self.counting_digest()
        core.plan_duplicates(self.cfg)                            # the work the dead service had done
        read = len(calls)
        gate = threading.Event()
        old.jobs.start('plan-duplicates', lambda progress: gate.wait(5))      # ...and it was still running
        new = server.App(self.cfg)                                # the deploy: a new service, same state folder
        new.jobs.resume_interrupted()
        for _ in range(300):
            if new.jobs.status()['state'] != 'running':
                break
            time.sleep(0.02)
        job = new.jobs.status()
        self.assertEqual((job['kind'], job['state']), ('plan-duplicates', 'done'))
        self.assertEqual(len(calls), read)                        # the resumed scan read nothing again
        self.assertEqual(new.jobs.plan(job['result']['plan'])['stats']['groups'], 4)
        log = {a['id']: a for a in new.jobs.activity()}
        cut = next(a for a in log.values() if a['state'] == 'interrupted')
        self.assertEqual(cut['resumed_by'], job['id'])
        self.assertEqual(log[job['id']]['resumed'], cut['id'])
        gate.set()
        old.jobs.job and time.sleep(0.05)

    def leave_running(self, **job):
        """A job record as a killed service leaves it: still 'running', with no thread behind it."""
        record = {'id': uuid.uuid4().hex[:12], 'state': 'running', 'started': time.time(), 'done': 0, 'total': 0,
                  'message': 'x', 'result': None, 'error': None, **job}
        (self.state / 'jobs').mkdir(exist_ok=True)
        (self.state / 'jobs' / f'{record["id"]}.json').write_text(json.dumps(record))

    def test_an_apply_is_never_restarted_by_itself(self):
        self.leave_running(kind='apply', plan='p1')
        service = server.App(self.cfg)
        service.jobs.resume_interrupted()
        self.assertIsNone(service.jobs.status())
        self.assertEqual(service.jobs.activity()[0]['state'], 'interrupted')

    def test_a_scan_that_was_already_a_resume_is_not_resumed_again_so_a_crash_cannot_loop(self):
        self.leave_running(kind='plan-sort', resumed='earlier')
        service = server.App(self.cfg)
        service.jobs.resume_interrupted()
        self.assertIsNone(service.jobs.status())


class BigDuplicatePlans(Library):
    """A library's worth of duplicates must load in seconds, and ticking one group must not re-read the disk."""

    def test_bulk_partners_agree_with_looking_one_up_at_a_time(self):
        for name in ('IMG_1.HEIC', 'IMG_1.MOV', 'IMG_2.jpg', 'IMG_3.HEIC', 'IMG_3.JPG', 'IMG_3.MOV', 'img_4.heic', 'IMG_4.MOV', 'lone.jpg'):
            self.put(f'a/{name}', name)
            self.put(f'b/{name}', name)
        paths = [str(p) for p in self.root.rglob('*') if p.is_file()]
        bulk = pairs.partners(paths)
        for p in paths:
            self.assertEqual(bulk.get(p), pairs.partner(p), p)
        self.assertIn(str(self.root / 'a/IMG_4.MOV'), bulk)          # case does not matter
        self.assertNotIn(str(self.root / 'a/IMG_3.MOV'), bulk)       # two stills: ambiguous, so none

    def test_showing_a_plan_reads_the_disk_once_and_a_tick_does_not_read_it_again(self):
        for i in range(3):
            self.put(f'library/2025/06/a{i}.jpg', f'same-{i}')
            self.put(f'library/2025/07/b{i}.jpg', f'same-{i}')
        app = server.App(self.cfg)
        app.jobs.start_plan('duplicates')
        for _ in range(300):
            if app.jobs.status()['state'] != 'running':
                break
            time.sleep(0.02)
        plan_id = app.jobs.status()['result']['plan']
        reads, real = [], core.live_mates
        core.live_mates = lambda cfg, plan: (reads.append(1), real(cfg, plan))[1]
        self.addCleanup(setattr, core, 'live_mates', real)
        before = app.route('GET', f'/api/plans/{plan_id}', {}, {})[1]
        self.assertEqual((before['preview']['moves'], before['selected']), (3, 3))
        app.route('PATCH', f'/api/plans/{plan_id}', {}, {'groups': ['d1'], 'selected': False})
        after = app.route('GET', f'/api/plans/{plan_id}', {}, {})[1]
        self.assertEqual((after['preview']['moves'], after['selected']), (2, 2))    # the tick took effect...
        self.assertEqual(len(reads), 1)                                              # ...without reading the disk again
        # but applying works from the folder as it is then, never from the remembered answer
        reads.clear()
        fresh = core.selected_moves(app.jobs.plan(plan_id), self.cfg)
        self.assertEqual((len(fresh), len(reads)), (2, 1))


class LibraryFirst(Library):
    """A copy in the library is the one kept, and the page can narrow to where the copies are."""

    def setUp(self):
        super().setUp()
        self.app = server.App(self.cfg)
        # one group per case: (files in it)
        self.put('library/2025/06/Trip/in_event.jpg', 'g1')
        self.put('old_upload/2025/06/in_event.jpg', 'g1')                 # outside, a name like a library one
        self.put('library/Unsorted/odd.jpg', 'g2')                        # in the library, but not in YYYY/MM
        self.put('2025/06/odd.jpg', 'g2')                                 # a stray year folder beside the library
        self.put('library/2025/06/a.jpg', 'g3')
        self.put('library/2025/07/a.jpg', 'g3')                           # two in the library
        self.put('old_upload/x.jpg', 'g4')
        self.put('backup/x.jpg', 'g4')                                    # none in the library
        self.plan = core.plan_duplicates(self.cfg)
        self.plan.update(id='p1', excluded=[], excluded_kinds=[], applied=None)
        self.app.jobs.save_plan(self.plan)

    def group(self, member):
        return next(g for g in self.plan['groups'] if member in g['files'])

    def test_the_library_copy_is_the_one_kept_whatever_the_folders_are_called(self):
        self.assertEqual(self.group('library/2025/06/Trip/in_event.jpg')['keep'], 'library/2025/06/Trip/in_event.jpg')
        self.assertEqual(self.group('library/Unsorted/odd.jpg')['keep'], 'library/Unsorted/odd.jpg')   # not beaten by 2025/06/ outside
        self.assertEqual(core.duplicate_scope(self.cfg, ['library/a.jpg', 'x/a.jpg']), 'one')

    def test_groups_can_be_narrowed_to_where_their_copies_are(self):
        def ids(scope):
            return {g['files'][0] for g in server.matching_groups(self.plan, '', scope, self.cfg)}
        self.assertEqual(len(ids('')), 4)
        self.assertEqual(len(ids('library')), 3)                     # at least one copy in the library
        self.assertEqual(ids('outside'), {self.group('old_upload/x.jpg')['files'][0]})
        self.assertEqual(len(ids('multi')), 1)
        counts = server.scope_counts(self.plan, self.cfg)
        self.assertEqual(counts, {'all': 4, 'library': 3, 'outside': 1, 'multi': 1})

    def test_the_routes_filter_count_and_bulk_edit_by_scope(self):
        got = self.app.route('GET', '/api/plans/p1/groups', {'scope': ['outside']}, {})[1]
        self.assertEqual((got['total'], got['groups'][0]['files'][0] in ('backup/x.jpg', 'old_upload/x.jpg')), (1, True))
        self.assertEqual(self.app.route('GET', '/api/plans/p1', {}, {})[1]['scopes']['library'], 3)
        # un-tick only the groups with a copy in the library
        self.app.route('PATCH', '/api/plans/p1', {}, {'filter': {'scope': 'library'}, 'selected': False})
        self.assertEqual(self.app.route('GET', '/api/plans/p1', {}, {})[1]['selected'], 1)       # only the outside group is still ticked

    def test_reset_keepers_applies_todays_rule_to_a_plan_made_by_an_older_one(self):
        g = self.group('library/2025/06/Trip/in_event.jpg')
        plan = self.app.jobs.plan('p1')
        next(x for x in plan['groups'] if x['id'] == g['id'])['keep'] = 'old_upload/2025/06/in_event.jpg'   # the old rule picked an outside copy
        self.app.jobs.save_plan(plan)
        self.app.route('PATCH', '/api/plans/p1', {}, {'keep_reset': {}})
        again = self.app.jobs.plan('p1')
        self.assertEqual(next(x for x in again['groups'] if x['id'] == g['id'])['keep'], 'library/2025/06/Trip/in_event.jpg')


class FindAndEdit(Library):
    """Search the whole media folder, edit what is inside a photo, copy it from a reference, and undo it."""

    def setUp(self):
        super().setUp()
        self.app = server.App(self.cfg)
        metadata.forget_listing()
        self.put('library/2025/06/Lake/IMG_1.jpg', 'one', '2025:06:14 10:00:00')
        self.put('library/2025/06/Lake/IMG_2.jpg', 'two')
        self.put('library/2025/07/Beach/IMG_3.jpg', 'three')
        self.put('_no_date/_inbox/loose/scan.jpg', 'scan')
        self.put('old_upload/clip.mov', 'video')
        self.put('notes.txt', 'not media')
        self.sync_dates()

    def wait(self):
        for _ in range(300):
            job = self.app.jobs.status()
            if job['state'] != 'running':
                return job
            time.sleep(0.02)
        self.fail('the job never finished')

    def meta(self, rel):
        return metadata.read(self.cfg, [rel])[0]

    def edit(self, rels, **body):
        self.app.jobs.start_meta_edit(rels, body)
        job = self.wait()
        self.assertEqual(job['state'], 'done', job)
        return job

    # -- finding
    def test_search_matches_every_word_in_any_folder_and_pages(self):
        self.assertEqual(metadata.find(self.cfg)['total'], 5)                           # media only, not notes.txt
        self.assertEqual([f['name'] for f in metadata.find(self.cfg, 'lake img')['files']], ['IMG_1.jpg', 'IMG_2.jpg'])
        self.assertEqual(metadata.find(self.cfg, '', 'old_upload')['total'], 1)
        self.assertEqual(metadata.find(self.cfg, '', '', 'video')['total'], 1)
        self.assertEqual(metadata.find(self.cfg, '', '', 'photo')['total'], 4)
        page = metadata.find(self.cfg, '', '', '', 2, 2)
        self.assertEqual((page['total'], len(page['files'])), (5, 2))
        self.assertEqual(metadata.find(self.cfg, 'nothing like this')['total'], 0)

    def test_locations_are_read_from_the_forms_people_copy(self):
        for text in ('30.6280, -96.3344', '30.6280 -96.3344', ' 30.628,-96.3344 '):
            self.assertEqual(metadata.parse_location(text), (30.628, -96.3344))
        for bad in ('nowhere', '30.6', '91, 10', '10, 181'):
            with self.assertRaises(ValueError):
                metadata.parse_location(bad)

    # -- editing
    def test_a_date_a_location_and_a_description_are_written_into_the_file_and_read_back(self):
        self.edit(['library/2025/06/Lake/IMG_2.jpg'], date='2023-06-14', time='09:30', location='30.628, -96.3344', description='At the lake')
        got = self.meta('library/2025/06/Lake/IMG_2.jpg')
        self.assertEqual((got['taken'], got['lat'], got['lon'], got['description']), ('2023-06-14 09:30:00', 30.628, -96.3344, 'At the lake'))

    def test_a_day_only_edit_keeps_each_files_own_time_of_day(self):
        self.edit(['library/2025/06/Lake/IMG_1.jpg'], date='2024-01-02', time='08:15')       # IMG_1 gets a full moment first
        self.edit(['library/2025/06/Lake/IMG_1.jpg', 'library/2025/06/Lake/IMG_2.jpg'], date='2023-06-14', time='17:45', day_only=True)
        self.assertEqual(self.meta('library/2025/06/Lake/IMG_1.jpg')['taken'], '2023-06-14 08:15:00')   # its own time kept
        self.assertEqual(self.meta('library/2025/06/Lake/IMG_2.jpg')['taken'], '2023-06-14 17:45:00')   # had none: the given time

    def test_the_sidecar_is_edited_too_because_immich_trusts_it_over_the_photo(self):
        photo = self.put('library/2025/06/Lake/IMG_5.jpg', 'five')
        self.put('library/2025/06/Lake/IMG_5.jpg.xmp', '<xmp/>')
        self.edit(['library/2025/06/Lake/IMG_5.jpg'], location='10, 20')
        meta = json.loads((self.tmp / 'dates.json.meta').read_text())
        self.assertEqual((meta['library/2025/06/Lake/IMG_5.jpg']['lat'], meta['library/2025/06/Lake/IMG_5.jpg.xmp']['lat']), (10.0, 10.0))

    def test_a_southern_and_western_location_keeps_its_signs(self):
        self.edit(['library/2025/06/Lake/IMG_2.jpg'], location='-33.8688, 151.2093')
        got = self.meta('library/2025/06/Lake/IMG_2.jpg')
        self.assertEqual((got['lat'], got['lon']), (-33.8688, 151.2093))

    def test_a_file_that_cannot_hold_the_change_is_reported_and_left_as_it_was(self):
        self.put('library/2025/06/Lake/anim.gif', 'gif')
        os.environ['FAKE_CANNOT_WRITE'] = '.gif'
        job = self.edit(['library/2025/06/Lake/IMG_2.jpg', 'library/2025/06/Lake/anim.gif'], location='10, 20')
        self.assertEqual([f['src'] for f in job['result']['failed']], ['library/2025/06/Lake/anim.gif'])
        self.assertIsNone(self.meta('library/2025/06/Lake/anim.gif')['lat'])
        self.assertEqual(self.meta('library/2025/06/Lake/IMG_2.jpg')['lat'], 10.0)

    # -- copying from a reference
    def test_location_and_day_can_be_copied_from_a_reference_photo_to_many(self):
        self.edit(['library/2025/06/Lake/IMG_1.jpg'], date='2023-08-09', time='13:20', location='45.5, -122.6')      # the reference
        targets = ['library/2025/06/Lake/IMG_2.jpg', 'library/2025/07/Beach/IMG_3.jpg']
        self.edit(targets, copy_from='library/2025/06/Lake/IMG_1.jpg', copy=['location', 'date'], day_only=True)
        for t in targets:
            got = self.meta(t)
            self.assertEqual((got['lat'], got['lon'], got['taken'][:10]), (45.5, -122.6, '2023-08-09'))
        self.assertEqual(self.meta('library/2025/06/Lake/IMG_1.jpg')['taken'], '2023-08-09 13:20:00')    # the reference is untouched

    def test_copying_something_the_reference_does_not_have_is_refused_before_anything_changes(self):
        with self.assertRaises(ValueError):
            self.app.jobs.start_meta_edit(['library/2025/06/Lake/IMG_2.jpg'], {'copy_from': 'library/2025/07/Beach/IMG_3.jpg', 'copy': ['location']})
        with self.assertRaises(ValueError):
            self.app.jobs.start_meta_edit(['library/2025/06/Lake/IMG_2.jpg'], {})            # nothing to change
        self.assertIsNone(self.app.jobs.status())

    def test_only_photos_and_videos_in_the_media_folder_can_be_edited(self):
        for rels in (['notes.txt'], ['../outside.jpg'], ['missing.jpg'], []):
            with self.assertRaises(ValueError):
                self.app.jobs.start_meta_edit(rels, {'location': '1, 2'})
        with self.assertRaises(ValueError):
            self.app.jobs.start_meta_edit(['library/2025/06/Lake/IMG_2.jpg'], {'location': '1, 2'} | {'date': '2023-02-30'})

    # -- undo
    def test_undo_puts_back_what_the_edit_replaced_including_removing_what_was_not_there(self):
        rel = 'library/2025/06/Lake/IMG_1.jpg'                          # had a date, no location
        before = self.meta(rel)
        job = self.edit([rel], date='2020-01-01', location='1, 2', description='changed')
        self.assertEqual(self.meta(rel)['lat'], 1.0)
        self.app.jobs.start_undo(job['result']['run'])
        self.assertEqual(self.wait()['state'], 'done')
        after = self.meta(rel)
        self.assertEqual((after['taken'][:7], after['lat'], after['description']), (before['taken'][:7], None, ''))
        self.assertTrue(self.app.jobs.run(job['result']['run'])['undone'])

    def test_the_run_is_in_history_as_an_edit_with_its_count(self):
        job = self.edit(['library/2025/06/Lake/IMG_2.jpg', 'library/2025/07/Beach/IMG_3.jpg'], location='1, 2')
        run = next(r for r in self.app.jobs.runs() if r['id'] == job['result']['run'])
        self.assertEqual((run['kind'], run['counts']['edited']), ('metadata', 2))

    def test_undoing_a_video_puts_back_its_location_in_the_video_tag_too(self):
        before = {'DateTimeOriginal': '2022:02:20 05:52:40', 'lat': 46.7562, 'lon': -122.0799, 'description': ''}
        photo, video, none = (metadata._restore_args(before, False), metadata._restore_args(before, False, True),
                              metadata._restore_args({**before, 'lat': None, 'lon': None}, False, True))
        self.assertNotIn('-GPSCoordinates=46.7562, -122.0799', photo)
        self.assertIn('-GPSCoordinates=46.7562, -122.0799', video)       # real exiftool: a MOV keeps it there, found when undoing
        self.assertIn('-GPSCoordinates=', none)                          # no location before: the tag is cleared

    # -- the routes
    def test_the_routes_find_read_and_edit(self):
        got = self.app.route('GET', '/api/find', {'q': ['beach']}, {})[1]
        self.assertEqual((got['total'], 'library' in got['folders']), (1, True))
        rows = self.app.route('POST', '/api/meta/read', {}, {'paths': ['library/2025/06/Lake/IMG_1.jpg']})[1]['files']
        self.assertEqual((rows[0]['taken'][:7], rows[0]['lat']), ('2025-06', None))
        self.assertNotIn('raw', rows[0])
        status, doc = self.app.route('POST', '/api/meta/edit', {}, {'paths': ['library/2025/06/Lake/IMG_2.jpg'], 'location': '5, 6'})
        self.assertEqual(status, 202)
        self.assertEqual(self.wait()['state'], 'done')
        with self.assertRaises(ValueError):
            self.app.route('POST', '/api/meta/read', {}, {'paths': ['notes.txt']})


class RescanAfterChanges(Library):
    """Whatever changes the library, Immich is asked to look again: new files, files that left, files that came back."""

    def setUp(self):
        super().setUp()
        self.fake = FakeImmich([], libraries=[{'id': 'lib1', 'name': 'Personal library', 'importPaths': ['/mnt/mahir-personal/library']}])
        self.addCleanup(self.fake.stop) if hasattr(self.fake, 'stop') else None
        self.app = server.App(self.cfg, immich=immich.Immich(self.fake.url, 'k3y'))

    def scans(self):
        return [c for c in self.fake.calls if c[0] == 'POST' and c[1].endswith('/scan')]

    def wait(self):
        for _ in range(300):
            job = self.app.jobs.status()
            if job['state'] != 'running':
                return job
            time.sleep(0.02)
        self.fail('the job never finished')

    def plan_and_apply(self, kind):
        self.app.jobs.start_plan(kind)
        plan_id = self.wait()['result']['plan']
        self.app.jobs.start_apply(plan_id)
        return self.wait()

    def test_filing_duplicates_out_of_the_library_asks_immich_to_rescan(self):
        self.put('library/2025/06/a.jpg', 'same bytes')
        self.put('library/2025/07/b.jpg', 'same bytes')
        job = self.plan_and_apply('duplicates')
        self.assertEqual(job['state'], 'done', job)
        self.assertEqual(len(self.scans()), 1)
        self.assertEqual(job['result']['immich_scan']['status'], 'queued')
        self.assertEqual(self.app.jobs.run(job['result']['run'])['immich_scan']['library'], 'Personal library')

    def test_deleting_from_the_library_or_removing_trashed_photos_asks_for_a_rescan_too(self):
        run = {'moves': [{'src': 'library/2025/03/IMG_1.JPG', 'dst': '', 'status': 'deleted'}]}
        self.assertTrue(self.app.jobs._touched_library(run))
        self.assertEqual(self.app.jobs._rescan(run)['status'], 'queued')
        self.assertEqual(len(self.scans()), 1)

    def test_a_run_that_never_touched_the_library_does_not(self):
        self.put('_inbox/loose/new.jpg', 'x')                          # no date: goes to _no_date, nowhere near the library
        job = self.plan_and_apply('sort')
        self.assertEqual(job['state'], 'done', job)
        self.assertEqual(self.scans(), [])
        self.assertNotIn('immich_scan', self.app.jobs.run(job['result']['run']))

    def test_undoing_a_run_that_changed_the_library_asks_again(self):
        self.put('library/2025/06/a.jpg', 'same bytes')
        self.put('library/2025/07/b.jpg', 'same bytes')
        job = self.plan_and_apply('duplicates')
        self.app.jobs.start_undo(job['result']['run'])
        undone = self.wait()
        self.assertEqual(undone['state'], 'done', undone)
        self.assertEqual(len(self.scans()), 2)                         # once to see them go, once to see them return
        self.assertEqual(undone['result']['immich_scan']['status'], 'queued')

    def test_editing_metadata_in_the_library_and_undoing_it_both_ask_for_a_rescan_but_edits_elsewhere_do_not(self):
        self.put('library/2025/06/a.jpg', 'photo bytes')
        self.put('old_upload/b.jpg', 'other photo')
        self.sync_dates()
        self.app.jobs.start_meta_edit(['library/2025/06/a.jpg'], {'location': '10, 20'})
        job = self.wait()
        self.assertEqual((job['state'], len(self.scans())), ('done', 1))
        self.app.jobs.start_undo(job['result']['run'])
        undone = self.wait()
        self.assertEqual((undone['state'], len(self.scans())), ('done', 2))          # the old values must reach Immich too
        self.assertEqual(undone['result']['immich_scan']['status'], 'queued')
        self.app.jobs.start_meta_edit(['old_upload/b.jpg'], {'location': '10, 20'})  # not in the library: Immich does not read it
        self.wait()
        self.assertEqual(len(self.scans()), 2)

    def test_without_immich_nothing_is_attempted_and_the_page_knows_not_to_promise_it(self):
        plain = server.App(self.cfg)
        self.assertIs(plain.route('GET', '/api/status', {}, {})[1]['immich'], False)
        self.assertIsNone(plain.jobs._rescan({'moves': [{'src': 'library/a.jpg', 'dst': '', 'status': 'deleted'}]}))
        self.assertIs(self.app.route('GET', '/api/status', {}, {})[1]['immich'], True)


class Pairs(unittest.TestCase):
    def test_pairing_is_by_folder_and_name(self):
        self.assertEqual(pairs.pairs(['/a/IMG_1.HEIC', '/a/IMG_1.MOV', '/b/IMG_1.MOV', '/a/IMG_2.MOV']),
                         {'/a/IMG_1.MOV': '/a/IMG_1.HEIC'})

    def test_two_stills_with_one_name_pair_with_neither(self):
        self.assertEqual(pairs.pairs(['/a/IMG_1.HEIC', '/a/IMG_1.JPG', '/a/IMG_1.MOV']), {})


class Api(Library):
    def setUp(self):
        super().setUp()
        self.app = server.App(self.cfg)

    def call(self, method, path, body=None, query=None):
        return self.app.route(method, path, query or {}, body or {})

    def wait(self):
        for _ in range(200):
            job = self.app.jobs.status()
            if job['state'] != 'running':
                return job
            time.sleep(0.02)
        self.fail('the job never finished')

    def test_plan_review_apply_undo_over_the_routes(self):
        self.put('_inbox/loose/IMG_1.HEIC', 'a', '2025-06')
        self.put('_inbox/loose/IMG_1.MOV', 'b', '2025-06')
        self.put('_inbox/loose/IMG_2.JPG', 'c', '2025-07')
        self.sync_dates()
        status, doc = self.call('POST', '/api/plans', {'kind': 'sort'})
        self.assertEqual(status, 202)
        job = self.wait()
        self.assertEqual(job['state'], 'done', job)
        plan_id = job['result']['plan']
        status, plan = self.call('GET', f'/api/plans/{plan_id}')
        self.assertEqual((plan['moves'], plan['selected']), (3, 3))
        _, listing = self.call('GET', f'/api/plans/{plan_id}/moves', query={'limit': ['2']})
        self.assertEqual((listing['total'], len(listing['moves'])), (3, 2))
        # untick IMG_2, then apply
        self.call('PATCH', f'/api/plans/{plan_id}', {'groups': ['m2'], 'selected': False})
        self.assertEqual(self.call('GET', f'/api/plans/{plan_id}')[1]['selected'], 2)
        self.call('POST', f'/api/plans/{plan_id}/apply')
        job = self.wait()
        self.assertEqual(job['state'], 'done', job)
        self.assertEqual(self.tree(), ['_inbox/loose/IMG_2.JPG', 'library/2025/06/IMG_1.HEIC',
                                       'library/2025/06/IMG_1.MOV'])
        with self.assertRaises(ValueError):
            self.call('POST', f'/api/plans/{plan_id}/apply')      # a plan is applied once
        run_id = job['result']['run']
        self.assertEqual(self.call('GET', '/api/runs')[1]['runs'][0]['counts']['moved'], 2)
        self.call('POST', f'/api/runs/{run_id}/undo')
        self.assertEqual(self.wait()['state'], 'done')
        self.assertEqual(len(self.tree()), 3)
        self.assertTrue(all(t.startswith('_inbox/') for t in self.tree()))

    def test_only_one_job_runs_at_a_time(self):
        gate = threading.Event()
        self.app.jobs.start('slow', lambda progress: gate.wait(5))
        with self.assertRaises(jobs.Busy):
            self.call('POST', '/api/plans', {'kind': 'sort'})
        gate.set()
        self.wait()

    def test_an_unknown_plan_is_a_404_not_a_path_walk(self):
        self.assertEqual(self.call('GET', '/api/plans/..%2f..%2fetc')[0], 404)
        with self.assertRaises(jobs.Missing):
            self.call('GET', '/api/plans/nosuchplan')
        self.assertEqual(self.call('GET', '/api/nope')[0], 404)

    def test_the_token_is_required_when_one_is_set(self):
        import http.client
        from http.server import ThreadingHTTPServer
        secured = server.App(self.cfg, token='s3cret')
        srv = ThreadingHTTPServer(('127.0.0.1', 0), server.handler(secured))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            def get(path, headers=None):
                c = http.client.HTTPConnection('127.0.0.1', srv.server_port)
                c.request('GET', path, headers=headers or {})
                r = c.getresponse()
                r.read()
                return r.status
            self.assertEqual(get('/api/status'), 401)
            self.assertEqual(get('/api/status', {'X-Autolab-Photos-Token': 'wrong'}), 401)
            self.assertEqual(get('/api/status', {'X-Autolab-Photos-Token': 's3cret'}), 200)
            self.assertEqual(get('/../../etc/passwd'), 404)
        finally:
            srv.shutdown()


if __name__ == '__main__':
    unittest.main()
