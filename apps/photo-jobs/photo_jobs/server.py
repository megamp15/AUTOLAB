"""The HTTP side: a small JSON API and the page. Standard library only.

Who may use it is decided in front of it (Traefik and Pocket ID). As a second lock, when
PHOTO_JOBS_TOKEN is set every API call must carry it in X-Autolab-Photos-Token, so reaching the
container's port directly gets nothing.
"""
import hmac
import json
import mimetypes
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import albums, core, metadata, nodate, previews
from .immich import Immich, ImmichError
from .jobs import Busy, Jobs, Missing

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'web')
MAX_BODY = 1 << 20


def inbox_counts(cfg):
    def count(*parts):
        base = os.path.join(cfg.root, *parts)
        return sum(1 for p in core.files_under(base) if core.is_media(p)) if os.path.isdir(base) else 0
    return {'loose': count(*core.LOOSE), 'events': count(*core.EVENTS), 'no_date': count(core.NODATE),
            'duplicates': count(core.DUPS)}


def group_key(move):
    return move.get('group') or f'm{move["id"]}'


def matching(plan, cfg, kind='', pair=False, text='', dup=None):
    """The plan's moves that pass a filter: a kind, Live Photos only, and/or text in a path or reason."""
    moves = (dup or (lambda p: core.duplicate_moves(cfg, p)))(plan)[0] if plan['kind'] == 'duplicates' else plan['moves']
    text = text.lower()
    return [m for m in moves if (not kind or m['kind'] == kind)
            and (not pair or (m.get('group') or '').startswith('pair:'))
            and (not text or text in m['src'].lower() or text in m['dst'].lower() or text in m['why'].lower())]


def matching_groups(plan, text='', scope='', cfg=None):
    """The duplicate groups with a file whose path contains the text (all of them for no text), and,
    for a scope, only those whose copies are where it says: 'library' (at least one copy in the
    library), 'outside' (none in it) or 'multi' (more than one in it)."""
    text, lib = text.lower(), (cfg.library if cfg else 'library') + '/'
    def where(g):
        n = sum(1 for f in g['files'] if f.startswith(lib))
        return {'library': n >= 1, 'outside': n == 0, 'multi': n >= 2}.get(scope, True)
    return [g for g in plan['groups'] if where(g) and (not text or any(text in f.lower() for f in g['files']))]


def scope_counts(plan, cfg):
    """How many groups each scope holds, for the filter chips."""
    c = {'all': len(plan['groups']), 'library': 0, 'outside': 0, 'multi': 0}
    for g in plan['groups']:
        n = sum(1 for f in g['files'] if core.in_library(cfg, f))
        c['library'] += n >= 1
        c['outside'] += n == 0
        c['multi'] += n >= 2
    return c


def item_on(plan, item):
    return f'immich:{item["id"]}' not in set(plan.get('excluded', []))


def matching_items(plan, status='', live=False, text=''):
    text = text.lower()
    return [i for i in plan['items'] if (not status or i['status'] == status) and (not live or i['clip'])
            and (not text or text in (i['name'] or '').lower() or text in (i['immich_path'] or '').lower())]


class App:
    def __init__(self, cfg, token='', immich=None):
        self.cfg, self.token, self.immich = cfg, token, immich
        self.jobs = Jobs(cfg, immich)
        self.started = time.time()
        self.dup_view = self.dup_mates = None

    def duplicate_view(self, plan):
        """What a duplicates plan would do, for showing. Working it out looks at the disk for every
        file in the plan, so the answer is kept for a minute for the same choices; an apply never
        uses it, it works from the folder as it is at that moment."""
        sig = (plan['id'], plan.get('mode'), tuple(plan.get('excluded', [])), tuple(plan.get('excluded_kinds', [])),
               hash(tuple(g['keep'] for g in plan['groups'])))
        hit = self.dup_view
        if hit and hit[0] == sig and time.time() - hit[1] < 60:
            return hit[2]
        mates = self.dup_mates
        if not (mates and mates[0] == plan['id'] and time.time() - mates[1] < 120):
            mates = self.dup_mates = (plan['id'], time.time(), core.live_mates(self.cfg, plan))   # the part that reads the disk
        result = core.duplicate_moves(self.cfg, plan, mates[2])
        self.dup_view = (sig, time.time(), result)
        return result

    def media(self, rel):
        """A photo or video inside the media folder, or an error: the page may ask about nothing else."""
        if not core.is_media(rel):
            raise ValueError(f'not a photo or video: {rel}')
        self.cfg.abs(rel)

    # Each route returns (status, document).
    def route(self, method, path, query, body):
        j, cfg = self.jobs, self.cfg
        if method == 'GET' and path == '/api/status':
            return 200, {'root': cfg.root, 'library': cfg.library, 'inbox': inbox_counts(cfg), 'job': j.status()}
        if method == 'GET' and path == '/api/immich':
            if not (self.immich and self.immich.configured):
                return 200, {'configured': False}
            try:
                return 200, {'configured': True, 'connected': True, **self.immich.check()}
            except ImmichError as e:
                return 200, {'configured': True, 'connected': False, 'error': str(e)}
        if method == 'GET' and path == '/api/albums':
            if not (self.immich and self.immich.configured):
                return 200, {'configured': False, 'events': []}
            return 200, {'configured': True, 'events': albums.review(cfg, self.immich)}
        if method == 'POST' and path == '/api/albums/scan':
            if not (self.immich and self.immich.configured):
                return 400, {'error': 'Immich is not connected'}
            return 202, {'scan': albums.scan_external_library(cfg, self.immich)}
        if method == 'POST' and path == '/api/albums':
            if not (self.immich and self.immich.configured):
                return 400, {'error': 'Immich is not connected'}
            selected = body.get('events', [])
            if not isinstance(selected, list) or not selected or len(selected) > 100:
                return 400, {'error': 'select between 1 and 100 event folders'}
            return 200, albums.create(cfg, self.immich, selected)
        one = lambda k: query.get(k, [''])[0]
        if method == 'GET' and path == '/api/info':
            self.media(one('path'))
            return 200, previews.facts(cfg, one('path'))
        if method == 'GET' and path == '/api/same':
            self.media(one('a')), self.media(one('b'))
            return 200, {'same': previews.same_bytes(cfg, one('a'), one('b'))}
        if method == 'GET' and path == '/api/find':
            found = metadata.find(cfg, one('q'), one('folder'), one('kind'), max(0, int(one('offset') or 0)), min(int(one('limit') or 60), metadata.MAX_FILES))
            return 200, {**found, 'folders': metadata.top_folders(cfg)}
        if method == 'POST' and path == '/api/meta/read':
            paths = body.get('paths', [])
            if not isinstance(paths, list) or len(paths) > 200:
                raise ValueError('paths must be a list of up to 200 files')
            for rel in paths:
                self.media(rel)
            return 200, {'files': [{k: v for k, v in r.items() if k != 'raw'} for r in metadata.read(cfg, paths)]}
        if method == 'POST' and path == '/api/meta/edit':
            return 202, {'job': j.start_meta_edit(body.get('paths', []), body)}
        if method == 'GET' and path == '/api/nodate':
            found = nodate.files(cfg)
            return 200, {'total': len(found), 'files': found}
        if method == 'POST' and path == '/api/nodate/date':
            paths = body.get('paths', [])
            if not isinstance(paths, list) or len(paths) > 2000:
                raise ValueError('paths must be a list of up to 2000 files')
            return 202, {'job': j.start_set_dates(paths, str(body.get('date', '')), str(body.get('time', '')))}
        if method == 'GET' and path == '/api/job':
            return 200, {'job': j.status()}
        if method == 'GET' and path == '/api/activity':
            return 200, {'activity': j.activity()}
        if method == 'POST' and path == '/api/job/cancel':
            return 200, {'job': j.cancel()}
        if method == 'GET' and path == '/api/plans':
            return 200, {'plans': j.plans()}
        if method == 'POST' and path == '/api/plans':
            return 202, {'job': j.start_plan(body.get('kind', ''))}
        m = re.fullmatch(r'/api/plans/([\w-]+)', path)
        if m and method == 'GET':
            plan = j.plan(m.group(1))
            out = j.summary(plan)
            if plan['kind'] == 'immich':
                out['selected_items'] = sum(1 for i in plan['items'] if i['status'] == 'file' and item_on(plan, i))
            if plan['kind'] == 'duplicates':
                moves, protected = self.duplicate_view(plan)
                out['preview'] = {'moves': len(moves), 'protected': protected[:50], 'protected_count': len(protected)}
                out['scopes'] = scope_counts(plan, cfg)
            elif plan['kind'] == 'sort':
                out['notes'] = plan['notes']
                out['left'] = plan['left'][:200]
            else:
                out['notes'] = plan['notes']
            out['selected'] = len(core.selected_moves(plan, cfg, moves if plan['kind'] == 'duplicates' else None))
            return 200, out
        m = re.fullmatch(r'/api/plans/([\w-]+)/moves', path)
        if m and method == 'GET':
            plan = j.plan(m.group(1))
            one = lambda k: query.get(k, [''])[0]
            rows = matching(plan, cfg, one('kind'), one('pair') == '1', one('q'), self.duplicate_view)
            off, lim = int(one('offset') or 0), min(int(one('limit') or 100), 500)
            excluded, kinds = set(plan.get('excluded', [])), set(plan.get('excluded_kinds', []))
            on = lambda x: group_key(x) not in excluded and x['kind'] not in kinds
            return 200, {'total': len(rows), 'selected': sum(1 for x in rows if on(x)), 'offset': off,
                         'moves': [{**x, 'selected': on(x)} for x in rows[off:off + lim]]}
        m = re.fullmatch(r'/api/plans/([\w-]+)/items', path)
        if m and method == 'GET':
            plan = j.plan(m.group(1))
            if plan['kind'] != 'immich':
                return 404, {'error': 'only Immich plans have items'}
            one = lambda k: query.get(k, [''])[0]
            rows = matching_items(plan, one('status'), one('live') == '1', one('q'))
            off, lim = int(one('offset') or 0), min(int(one('limit') or 100), 500)
            return 200, {'total': len(rows), 'offset': off,
                         'selected': sum(1 for i in rows if i['status'] == 'file' and item_on(plan, i)),
                         'selectable': sum(1 for i in rows if i['status'] == 'file'),
                         'items': [{**i, 'selected': item_on(plan, i)} for i in rows[off:off + lim]]}
        m = re.fullmatch(r'/api/plans/([\w-]+)/groups', path)
        if m and method == 'GET':
            plan = j.plan(m.group(1))
            if plan['kind'] != 'duplicates':
                return 404, {'error': 'only duplicate plans have groups'}
            rows = matching_groups(plan, query.get('q', [''])[0], query.get('scope', [''])[0], cfg)
            off, lim = int(query.get('offset', ['0'])[0]), min(int(query.get('limit', ['50'])[0]), 200)
            excluded = set(plan.get('excluded', []))
            return 200, {'total': len(rows), 'offset': off,
                         'selected': sum(1 for g in rows if g['id'] not in excluded),
                         'groups': [{**g, 'selected': g['id'] not in excluded} for g in rows[off:off + lim]]}
        m = re.fullmatch(r'/api/plans/([\w-]+)', path)
        if m and method == 'PATCH':
            plan = j.plan(m.group(1))
            if plan.get('applied'):
                return 409, {'error': 'already applied'}
            if j.job and j.job['state'] == 'running' and j.job.get('plan') == plan['id']:
                return 409, {'error': 'this scan is still running; choices open when it finishes'}
            excluded = set(plan.get('excluded', []))
            kinds = set(plan.get('excluded_kinds', []))
            for key in body.get('groups', []):
                (excluded.discard if body.get('selected') else excluded.add)(key)
            if 'filter' in body:   # everything that passes the filter, not only what the page has loaded
                f = body['filter']
                keys = ([f'immich:{i["id"]}' for i in matching_items(plan, f.get('status', ''), bool(f.get('live')), f.get('q', ''))]
                        if plan['kind'] == 'immich' else
                        [g['id'] for g in matching_groups(plan, f.get('q', ''), f.get('scope', ''), cfg)] if plan['kind'] == 'duplicates' else
                        [group_key(x) for x in matching(plan, cfg, f.get('kind', ''), bool(f.get('pair')), f.get('q', ''), self.duplicate_view)])
                for key in keys:
                    (excluded.discard if body.get('selected') else excluded.add)(key)
            if 'kind' in body:
                (kinds.discard if body.get('selected') else kinds.add)(body['kind'])
            if body.get('all') is not None:
                excluded.clear(); kinds.clear()
                if not body['all']:
                    if plan['kind'] == 'immich':
                        excluded.update(f'immich:{i["id"]}' for i in plan['items'])
                    else:
                        kinds.update({x['kind'] for x in plan['moves']} if plan['kind'] == 'sort' else {'duplicate'})
            if 'mode' in body:
                if plan['kind'] not in ('duplicates', 'immich') or body['mode'] not in ('file', 'delete'):
                    return 400, {'error': 'mode is "file" or "delete", and only for duplicates or Immich plans'}
                plan['mode'] = body['mode']
            if 'keep' in body and plan['kind'] == 'duplicates':
                for gid, rel in body['keep'].items():
                    g = next((x for x in plan['groups'] if x['id'] == gid), None)
                    if g and rel in g['files']:
                        g['keep'] = rel
            changed = 0
            if plan['kind'] == 'duplicates' and ('keep_where' in body or 'keep_reset' in body):
                # Bulk keepers, over the groups the search box is showing. Files in a group are
                # listed best copy first, so "the best copy in this folder" is the first that matches.
                rule = body.get('keep_where') or body.get('keep_reset') or {}
                frag = (body.get('keep_where') or {}).get('contains', '').strip().lower()
                if 'keep_where' in body and not frag:
                    return 400, {'error': 'say which folder or path to keep copies in'}
                for g in matching_groups(plan, rule.get('q', ''), rule.get('scope', ''), cfg):
                    ranked = sorted(g['files'], key=lambda f: core._rank(cfg, f))      # by today's rule, not the one the scan used
                    pick = next((f for f in ranked if frag in f.lower()), None) if frag else ranked[0]
                    if pick and pick != g['keep']:
                        g['keep'] = pick
                        changed += 1
            plan['excluded'], plan['excluded_kinds'] = sorted(excluded), sorted(kinds)
            j.save_plan(plan)
            return 200, {'ok': True, 'changed': changed}
        m = re.fullmatch(r'/api/plans/([\w-]+)/apply', path)
        if m and method == 'POST':
            plan = j.plan(m.group(1))
            if plan.get('mode') == 'delete' and body.get('confirm') != 'DELETE':
                return 400, {'error': 'deleting needs confirm: "DELETE"; it cannot be undone'}
            return 202, {'job': j.start_apply(m.group(1))}
        if method == 'GET' and path == '/api/runs':
            return 200, {'runs': j.runs()}
        m = re.fullmatch(r'/api/runs/([\w-]+)', path)
        if m and method == 'GET':
            run = j.run(m.group(1))
            return 200, {**{k: v for k, v in run.items() if k != 'moves'}, 'moves': run['moves'][:300],
                         'total_moves': len(run['moves'])}
        m = re.fullmatch(r'/api/runs/([\w-]+)/undo', path)
        if m and method == 'POST':
            return 202, {'job': j.start_undo(m.group(1))}
        return 404, {'error': 'not found'}


def handler(app):
    class H(BaseHTTPRequestHandler):
        server_version = 'photo-jobs'

        def log_message(self, fmt, *args):
            sys.stderr.write('%s %s\n' % (self.address_string(), fmt % args))

        def send(self, status, doc, ctype='application/json'):
            data = json.dumps(doc).encode() if ctype == 'application/json' else doc
            self.send_response(status)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)

        def stream(self, file, ctype, cache):
            """Send a file, honouring a Range header so a video can seek."""
            size = os.path.getsize(file)
            start, end, status = 0, size - 1, 200
            m = re.fullmatch(r'bytes=(\d*)-(\d*)', (self.headers.get('Range') or '').strip())
            if m and (m.group(1) or m.group(2)):
                a, b = m.groups()
                start, end = (max(0, size - int(b)), size - 1) if not a else (int(a), min(int(b), size - 1) if b else size - 1)
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{size}')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                status = 206
            self.send_response(status)
            self.send_header('Content-Type', ctype)
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(end - start + 1))
            if status == 206:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.send_header('Cache-Control', cache)
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            try:
                with open(file, 'rb') as f:
                    f.seek(start)
                    left = end - start + 1
                    while left > 0:
                        chunk = f.read(min(1 << 16, left))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass   # the viewer closed the picture or seeked elsewhere

        def binary(self, path, query):
            rel = query.get('path', [''])[0]
            try:
                if not (path == '/api/preview' and os.path.isdir(app.cfg.abs(rel))):   # a preview may be of a folder
                    app.media(rel)
                if path == '/api/preview':
                    file = previews.thumbnail(app.cfg, rel, int(query.get('w', ['240'])[0] or 240))
                    return self.stream(file, mimetypes.guess_type(file)[0] or 'image/jpeg', 'private, max-age=86400')
                return self.stream(app.cfg.abs(rel), mimetypes.guess_type(rel)[0] or 'application/octet-stream', 'private, max-age=300')
            except previews.NoPreview:
                return self.send(404, {'error': 'no preview'})
            except FileNotFoundError:
                return self.send(404, {'error': 'not found'})
            except ValueError as e:
                return self.send(400, {'error': str(e)})

        def dispatch(self, method):
            url = urlparse(self.path)
            if url.path.startswith('/api/'):
                if app.token and not hmac.compare_digest(self.headers.get('X-Autolab-Photos-Token', ''), app.token):
                    return self.send(401, {'error': 'unauthorised'})
                if method == 'GET' and url.path in ('/api/preview', '/api/file'):
                    return self.binary(url.path, parse_qs(url.query))
                body = {}
                if method in ('POST', 'PATCH'):
                    n = int(self.headers.get('Content-Length') or 0)
                    if n > MAX_BODY:
                        return self.send(413, {'error': 'body too large'})
                    try:
                        body = json.loads(self.rfile.read(n) or b'{}')
                    except ValueError:
                        return self.send(400, {'error': 'invalid JSON'})
                try:
                    status, doc = app.route(method, url.path, parse_qs(url.query), body)
                except (Missing, FileNotFoundError):
                    status, doc = 404, {'error': 'not found'}
                except Busy as e:
                    status, doc = 409, {'error': f'a {e} job is already running'}
                except (ValueError, KeyError) as e:
                    status, doc = 400, {'error': str(e)}
                except ImmichError as e:
                    status, doc = 502, {'error': str(e)}
                return self.send(status, doc)
            if method != 'GET':
                return self.send(405, {'error': 'method not allowed'})
            name = 'index.html' if url.path in ('/', '') else url.path.lstrip('/')
            path = os.path.normpath(os.path.join(WEB, name))
            if not path.startswith(os.path.normpath(WEB) + os.sep) or not os.path.isfile(path):
                return self.send(404, {'error': 'not found'})
            with open(path, 'rb') as f:
                self.send(200, f.read(), mimetypes.guess_type(path)[0] or 'application/octet-stream')

        def do_GET(self): self.dispatch('GET')
        def do_POST(self): self.dispatch('POST')
        def do_PATCH(self): self.dispatch('PATCH')
        def do_PUT(self): self.dispatch('PUT')
    return H


def main():
    cfg = core.Config(os.environ.get('MEDIA_ROOT', '/media'), os.environ.get('STATE_DIR', '/state'),
                      os.environ.get('LIBRARY', 'library'), os.environ.get('IMMICH_MEDIA_PREFIX', '/mnt/mahir-personal'))
    immich = Immich(os.environ.get('IMMICH_URL', ''), os.environ.get('IMMICH_API_KEY', ''))
    app = App(cfg, os.environ.get('PHOTO_JOBS_TOKEN', ''), immich)
    app.jobs.resume_interrupted()
    host, port = os.environ.get('BIND', '0.0.0.0'), int(os.environ.get('PORT', '8099'))
    srv = ThreadingHTTPServer((host, port), handler(app))
    print(f'photo-jobs on {host}:{port}, media {cfg.root}, state {cfg.state}', flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()
