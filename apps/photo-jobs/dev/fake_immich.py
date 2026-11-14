"""A stand-in for Immich's API: just the key check, who you are, and a paged search of the trash.

Used by the tests and by dev/demo.py so the Immich tab can be tried without an Immich server.
legacy=True behaves like an older server that rejects the current `filter` search.
"""
import base64
import hashlib
import json
import threading


class FakeImmich:
    def __init__(self, assets, legacy=False, key='k3y'):
        import http.server
        self.assets, self.legacy, self.key, self.calls = assets, legacy, key, []
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
                if self.path == '/api/users/me':
                    return self.reply(200, {'email': 'me@example.com'})
                if self.path == '/api/server/about':
                    return self.reply(200, {'version': 'v3.4.1'})
                if self.path == '/api/search/metadata':
                    if outer.legacy and 'filter' in body:
                        return self.reply(400, {'message': 'property filter should not exist'})
                    size, page = body['size'], body['page']
                    items = [a for a in outer.assets if a.get('isTrashed')] if ('filter' in body or body.get('withDeleted')) else \
                            [a for a in outer.assets if not a.get('isTrashed')]
                    chunk = items[(page - 1) * size:page * size]
                    more = page * size < len(items)
                    return self.reply(200, {'assets': {'items': chunk, 'total': len(items),
                                                       'nextPage': str(page + 1) if more else None}})
                self.reply(404, {})

            do_GET = do_POST = handle_any

        self.srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=lambda: self.srv.serve_forever(poll_interval=0.01), daemon=True).start()
        self.url = f'http://127.0.0.1:{self.srv.server_port}'

    def stop(self):
        self.srv.shutdown()


def sha1b64(content):
    return base64.b64encode(hashlib.sha1(content.encode()).digest()).decode()
