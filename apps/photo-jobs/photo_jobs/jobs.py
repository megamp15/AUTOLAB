"""One background job at a time, with plans and runs kept as files.

State lives in <state>/plans/<id>.json and <state>/runs/<id>.json, so a restart loses nothing.
A job is something slow (scanning, applying, undoing); it reports progress the page polls for.
"""
import json
import os
import threading
import time
import uuid

from . import albums, core, nodate
from .immich import ImmichError


class Busy(Exception):
    pass


class Missing(Exception):
    pass


class Jobs:
    def __init__(self, cfg, immich=None):
        self.cfg, self.immich = cfg, immich
        self.lock = threading.Lock()
        self.job = None            # the current or most recent job
        self.cache = {}            # plan id -> plan
        for d in ('plans', 'runs'):
            os.makedirs(os.path.join(cfg.state, d), exist_ok=True)

    # -- files
    def _path(self, kind, id_):
        if not id_.replace('-', '').isalnum():
            raise Missing(id_)
        return os.path.join(self.cfg.state, kind, f'{id_}.json')

    def _save(self, kind, doc):
        path = self._path(kind, doc['id'])
        with open(path + '.tmp', 'w') as f:
            json.dump(doc, f)
        os.replace(path + '.tmp', path)

    def _load(self, kind, id_):
        try:
            with open(self._path(kind, id_)) as f:
                return json.load(f)
        except FileNotFoundError:
            raise Missing(id_)

    def _list(self, kind):
        out = []
        d = os.path.join(self.cfg.state, kind)
        for name in os.listdir(d):
            if name.endswith('.json'):
                try:
                    out.append(self._load(kind, name[:-5]))
                except (Missing, ValueError):
                    pass
        return sorted(out, key=lambda x: -x.get('created', x.get('started', 0)))

    # -- plans
    def plan(self, id_):
        if id_ not in self.cache:
            self.cache[id_] = self._load('plans', id_)
        return self.cache[id_]

    def save_plan(self, plan):
        self.cache[plan['id']] = plan
        self._save('plans', plan)

    def plans(self):
        return [self.summary(p) for p in self._list('plans')]

    def summary(self, plan):
        out = {k: v for k, v in plan.items() if k not in ('moves', 'groups', 'left', 'items')}
        out['moves'] = len(plan['moves']) if plan['kind'] == 'sort' else None
        out['groups'] = len(plan['groups']) if plan['kind'] == 'duplicates' else None
        out['items'] = len(plan['items']) if plan['kind'] == 'immich' else None
        return out

    def runs(self):
        return [{k: v for k, v in r.items() if k != 'moves'} | {
            'counts': {s: sum(1 for m in r['moves'] if m['status'] == s) for s in ('moved', 'deleted', 'skipped', 'error')}}
            for r in self._list('runs')]

    def run(self, id_):
        return self._load('runs', id_)

    # -- jobs
    def status(self):
        return dict(self.job) if self.job else None

    def start(self, kind, work, **info):
        """Run work(job) in a thread. Only one job runs at a time."""
        with self.lock:
            if self.job and self.job['state'] == 'running':
                raise Busy(self.job['kind'])
            job = {'id': uuid.uuid4().hex[:12], 'kind': kind, 'state': 'running', 'started': time.time(),
                   'done': 0, 'total': 0, 'message': 'starting', 'result': None, 'error': None, **info}
            self.job = job

        def progress(done=None, total=None, message=None):
            if done is not None:
                job['done'] = done
            if total is not None:
                job['total'] = total
            if message:
                job['message'] = message

        def target():
            try:
                job['result'] = work(progress)
                job['state'] = 'done'
                job['message'] = 'done'
            except Exception as e:   # noqa: BLE001 — a job's failure is data for the page, not a crash
                job['state'], job['error'] = 'error', f'{type(e).__name__}: {e}'
            job['finished'] = time.time()

        threading.Thread(target=target, daemon=True).start()
        return dict(job)

    # -- the three things a person does
    def start_plan(self, kind):
        if kind not in ('sort', 'duplicates', 'immich'):
            raise ValueError(f'unknown plan kind {kind}')
        if kind == 'immich' and not (self.immich and self.immich.configured):
            raise ValueError('Immich is not connected: set IMMICH_URL and IMMICH_API_KEY')

        def work(progress):
            plan = (core.plan_sort(self.cfg, progress) if kind == 'sort' else
                    core.plan_duplicates(self.cfg, progress) if kind == 'duplicates' else
                    core.plan_immich(self.cfg, self.immich, progress))
            plan.update(id=uuid.uuid4().hex[:12], created=time.time(), excluded=[], excluded_kinds=[], applied=None)
            self.save_plan(plan)
            return {'plan': plan['id']}

        return self.start('plan-' + kind, work)

    def start_apply(self, plan_id):
        plan = self.plan(plan_id)
        if plan.get('applied'):
            raise ValueError('this plan was already applied; make a new one')
        moves = core.selected_moves(plan, self.cfg)

        def work(progress):
            run_id = uuid.uuid4().hex[:12]

            def record(run):
                self._save('runs', {'id': run_id, 'plan': plan_id, 'kind': plan['kind'], **run})

            run = core.apply_moves(self.cfg, moves, progress, record)
            library_changed = plan['kind'] == 'sort' and any(
                move.get('status') == 'moved' and move.get('dst') and
                (move['dst'] == self.cfg.library or move['dst'].startswith(self.cfg.library + os.sep))
                for move in run['moves'])
            if library_changed and self.immich and self.immich.configured:
                try:
                    library = albums.scan_external_library(self.cfg, self.immich)
                    run['immich_scan'] = {'status': 'queued', 'library': library['name']}
                except (ImmichError, ValueError) as e:
                    run['immich_scan'] = {'status': 'failed', 'error': str(e)}
                self._save('runs', {'id': run_id, 'plan': plan_id, 'kind': plan['kind'], **run})
            plan['applied'] = run_id
            self.save_plan(plan)
            return {'run': run_id, 'immich_scan': run.get('immich_scan')}

        return self.start('apply', work, plan=plan_id)

    def start_undo(self, run_id):
        run = self.run(run_id)
        if run.get('undone'):
            raise ValueError('this run was already undone')

        def work(progress):
            result = core.undo_run(self.cfg, run, progress)
            run['undone'] = {'at': time.time(), **result}
            self._save('runs', run)
            return result

        return self.start('undo', work, run=run_id)

    def start_set_dates(self, rels, date, time=''):
        """Write a date into each of these _no_date files and send them to the inbox."""
        when = nodate.stamp(date, time)
        if not rels:
            raise ValueError('choose at least one photo')
        base = os.path.join(self.cfg.root, core.NODATE)
        for rel in rels:
            if not self.cfg.abs(rel).startswith(base + os.sep) or not core.is_media(rel):
                raise ValueError(f'not a photo set aside for having no date: {rel}')

        def work(progress):
            run_id = uuid.uuid4().hex[:12]

            def record(run):
                self._save('runs', {'id': run_id, 'plan': None, 'kind': 'set-date', **run})

            run = nodate.set_dates(self.cfg, rels, when, progress, record)
            return {'run': run_id, 'failed': [{'src': m['src'], 'note': m['note']} for m in run['moves'] if m['status'] == 'error'][:50]}

        return self.start('set-date', work)
