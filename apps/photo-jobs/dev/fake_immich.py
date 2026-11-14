"""A stand-in for Immich's API: just the key check, who you are, and a paged search of the trash.

Used by the tests and by dev/demo.py so the Immich tab can be tried without an Immich server.
legacy=True behaves like an older server that rejects the current `filter` search.
"""
import base64
import hashlib
import json
import threading
import uuid


class FakeImmich:
    def __init__(self, assets, legacy=False, key='k3y', albums=None, libraries=None, scan_assets=None, forbidden=()):
        import http.server
        self.assets, self.legacy, self.key, self.calls = assets, legacy, key, []
        self.forbidden = set(forbidden)   # paths this key lacks the permission for
        self.albums = albums or []
        self.libraries, self.scan_assets = libraries or [], scan_assets or []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def reply(self, code, doc):
                data = json.dumps(doc).encode()
                self.send_response(code); self.send_header('Content-Length', str(len(data))); self.end_headers()
                self.wfile.write(data)

            def handle_any(self):
                n = int(self.headers.get('Content-Length') or 0)
                body = json.loads(self.rfile.read(n) or b'{}')
                outer.calls.append((self.command, self.path, body, self.headers.get('x-api-key')))
                if self.headers.get('x-api-key') != outer.key:
                    return self.reply(401, {'message': 'Invalid API key'})
                if self.path in outer.forbidden:
                    return self.reply(403, {'message': 'Missing required permission'})
                if self.path == '/api/users/me':
                    return self.reply(200, {'email': 'me@example.com'})
                if self.path == '/api/server/about':
                    return self.reply(200, {'version': 'v3.4.1'})
                if self.path == '/api/search/metadata':
                    if outer.legacy and 'filter' in body:
                        return self.reply(400, {'message': 'property filter should not exist'})
                    size = body['size']
                    if 'filter' in body and 'page' in body:      # what Immich 3.x answers
                        return self.reply(400, {'message': 'Validation failed', 'errors': [
                            {'path': ['page'], 'message': 'Deprecated field page cannot be combined with filter'}]})
                    start = int(base64.b64decode(body['cursor'])) if body.get('cursor') else (body.get('page', 1) - 1) * size
                    filters = body.get('filter') or {}
                    items = [a for a in outer.assets if a.get('isTrashed')] if filters.get('trashedAt') or body.get('withDeleted') else \
                            [a for a in outer.assets if not a.get('isTrashed')]
                    path_filter = filters.get('originalPath', {}).get('startsWith')
                    if path_filter:
                        items = [a for a in items if a.get('originalPath', '').startswith(path_filter)]
                    album_filter = filters.get('albumIds', {}).get('in')
                    if album_filter:
                        ids = {asset_id for album in outer.albums if album['id'] in album_filter for asset_id in album['assetIds']}
                        items = [a for a in items if a['id'] in ids]
                    chunk = items[start:start + size]
                    more = start + size < len(items)
                    nxt = base64.b64encode(str(start + size).encode()).decode() if more else None
                    return self.reply(200, {'assets': {'items': chunk, 'total': len(items),
                                                       'nextPage': str(start // size + 2) if more and 'filter' not in body else None,
                                                       'nextCursor': nxt if 'filter' in body else None}})
                if self.path == '/api/libraries' and self.command == 'GET':
                    return self.reply(200, outer.libraries)
                if self.path.startswith('/api/libraries/') and self.path.endswith('/scan') and self.command == 'POST':
                    library_id = self.path.split('/')[-2]
                    if not any(library['id'] == library_id for library in outer.libraries):
                        return self.reply(404, {'message': 'Library not found'})
                    known = {asset['id'] for asset in outer.assets}
                    outer.assets.extend(asset for asset in outer.scan_assets if asset['id'] not in known)
                    return self.reply(204, {})
                if self.path == '/api/albums' and self.command == 'GET':
                    return self.reply(200, [{k: v for k, v in album.items() if k != 'assetIds'} |
                                            {'assetCount': len(album['assetIds'])} for album in outer.albums])
                if self.path == '/api/albums' and self.command == 'POST':
                    album = {'id': str(uuid.uuid4()), 'albumName': body['albumName'], 'assetIds': body.get('assetIds', [])}
                    outer.albums.append(album)
                    return self.reply(201, {k: v for k, v in album.items() if k != 'assetIds'} |
                                      {'assetCount': len(album['assetIds'])})
                if self.path.startswith('/api/albums/') and self.path.endswith('/assets') and self.command == 'PUT':
                    album_id = self.path.split('/')[-2]
                    album = next((a for a in outer.albums if a['id'] == album_id), None)
                    if not album:
                        return self.reply(404, {'message': 'Album not found'})
                    added = [asset_id for asset_id in body.get('assetIds', []) if asset_id not in album['assetIds']]
                    album['assetIds'].extend(added)
                    return self.reply(200, [{'assetId': asset_id, 'success': True} for asset_id in added])
                self.reply(404, {})

            do_GET = do_POST = do_PUT = handle_any

        self.srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=lambda: self.srv.serve_forever(poll_interval=0.01), daemon=True).start()
        self.url = f'http://127.0.0.1:{self.srv.server_port}'

    def stop(self):
        self.srv.shutdown()


def sha1b64(content):
    return base64.b64encode(hashlib.sha1(content.encode()).digest()).decode()
