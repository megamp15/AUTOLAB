#!/usr/bin/env python3
"""Photo Jobs against a throwaway library, with a stand-in exiftool.

The stand-in reads recording months from a JSON map (path -> YYYY-MM), so each test chooses what
every file claims to be, and needs no real photos. Planning, applying, undoing and the HTTP routes
are the real code.
"""
import json
import os
import shutil
import stat
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'apps/photo-jobs'
sys.path.insert(0, str(APP))

from photo_jobs import core, jobs, pairs, server  # noqa: E402

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
