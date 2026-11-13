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

from . import core
from .jobs import Busy, Jobs, Missing

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'web')
MAX_BODY = 1 << 20


def inbox_counts(cfg):
    def count(*parts):
        base = os.path.join(cfg.root, *parts)
        return sum(1 for p in core.files_under(base) if core.is_media(p)) if os.path.isdir(base) else 0
    return {'loose': count(*core.LOOSE), 'events': count(*core.EVENTS), 'no_date': count(core.NODATE),
            'duplicates': count(core.DUPS)}


class App:
    def __init__(self, cfg, token=''):
        self.cfg, self.token, self.jobs = cfg, token, Jobs(cfg)
        self.started = time.time()

    # Each route returns (status, document).
    def route(self, method, path, query, body):
        j, cfg = self.jobs, self.cfg
        if method == 'GET' and path == '/api/status':
            return 200, {'root': cfg.root, 'library': cfg.library, 'inbox': inbox_counts(cfg), 'job': j.status()}
        if method == 'GET' and path == '/api/job':
            return 200, {'job': j.status()}
        if method == 'GET' and path == '/api/plans':
            return 200, {'plans': j.plans()}
        if method == 'POST' and path == '/api/plans':
            return 202, {'job': j.start_plan(body.get('kind', ''))}
        m = re.fullmatch(r'/api/plans/([\w-]+)', path)
        if m and method == 'GET':
            plan = j.plan(m.group(1))
            out = j.summary(plan)
            if plan['kind'] == 'duplicates':
                moves, protected = core.duplicate_moves(cfg, plan)
                out['preview'] = {'moves': len(moves), 'protected': protected[:50], 'protected_count': len(protected)}
            else:
                out['notes'] = plan['notes']
                out['left'] = plan['left'][:200]
            out['selected'] = len(core.selected_moves(plan, cfg))
            return 200, out
        m = re.fullmatch(r'/api/plans/([\w-]+)/moves', path)
        if m and method == 'GET':
            plan = j.plan(m.group(1))
            moves = core.duplicate_moves(cfg, plan)[0] if plan['kind'] == 'duplicates' else plan['moves']
            kind, text = query.get('kind', [''])[0], query.get('q', [''])[0].lower()
            rows = [x for x in moves if (not kind or x['kind'] == kind)
                    and (not text or text in x['src'].lower() or text in x['dst'].lower() or text in x['why'].lower())]
            off, lim = int(query.get('offset', ['0'])[0]), min(int(query.get('limit', ['100'])[0]), 500)
            excluded, kinds = set(plan.get('excluded', [])), set(plan.get('excluded_kinds', []))
            page = [{**x, 'selected': (x.get('group') or f'm{x["id"]}') not in excluded and x['kind'] not in kinds}
                    for x in rows[off:off + lim]]
            return 200, {'total': len(rows), 'offset': off, 'moves': page}
        m = re.fullmatch(r'/api/plans/([\w-]+)/groups', path)
        if m and method == 'GET':
            plan = j.plan(m.group(1))
            if plan['kind'] != 'duplicates':
                return 404, {'error': 'only duplicate plans have groups'}
            text = query.get('q', [''])[0].lower()
            rows = [g for g in plan['groups'] if not text or any(text in f.lower() for f in g['files'])]
            off, lim = int(query.get('offset', ['0'])[0]), min(int(query.get('limit', ['50'])[0]), 200)
            excluded = set(plan.get('excluded', []))
            return 200, {'total': len(rows), 'offset': off,
                         'groups': [{**g, 'selected': g['id'] not in excluded} for g in rows[off:off + lim]]}
        m = re.fullmatch(r'/api/plans/([\w-]+)', path)
        if m and method == 'PATCH':
            plan = j.plan(m.group(1))
            if plan.get('applied'):
                return 409, {'error': 'already applied'}
            excluded = set(plan.get('excluded', []))
            kinds = set(plan.get('excluded_kinds', []))
            for key in body.get('groups', []):
                (excluded.discard if body.get('selected') else excluded.add)(key)
            if 'kind' in body:
                (kinds.discard if body.get('selected') else kinds.add)(body['kind'])
            if body.get('all') is not None:
                excluded.clear(); kinds.clear()
                if not body['all']:
                    kinds.update({x['kind'] for x in plan['moves']} if plan['kind'] == 'sort' else {'duplicate'})
            if 'keep' in body and plan['kind'] == 'duplicates':
                for gid, rel in body['keep'].items():
                    g = next((x for x in plan['groups'] if x['id'] == gid), None)
                    if g and rel in g['files']:
                        g['keep'] = rel
            plan['excluded'], plan['excluded_kinds'] = sorted(excluded), sorted(kinds)
            j.save_plan(plan)
            return 200, {'ok': True}
        m = re.fullmatch(r'/api/plans/([\w-]+)/apply', path)
        if m and method == 'POST':
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

        def dispatch(self, method):
            url = urlparse(self.path)
            if url.path.startswith('/api/'):
                if app.token and not hmac.compare_digest(self.headers.get('X-Autolab-Photos-Token', ''), app.token):
                    return self.send(401, {'error': 'unauthorised'})
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
                except Missing:
                    status, doc = 404, {'error': 'not found'}
                except Busy as e:
                    status, doc = 409, {'error': f'a {e} job is already running'}
                except (ValueError, KeyError) as e:
                    status, doc = 400, {'error': str(e)}
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
    return H


def main():
    cfg = core.Config(os.environ.get('MEDIA_ROOT', '/media'), os.environ.get('STATE_DIR', '/state'),
                      os.environ.get('LIBRARY', 'library'))
    app = App(cfg, os.environ.get('PHOTO_JOBS_TOKEN', ''))
    host, port = os.environ.get('BIND', '0.0.0.0'), int(os.environ.get('PORT', '8099'))
    srv = ThreadingHTTPServer((host, port), handler(app))
    print(f'photo-jobs on {host}:{port}, media {cfg.root}, state {cfg.state}', flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()
