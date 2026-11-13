#!/usr/bin/env python3
"""Local homepage review using live, read-only monitoring sources. No deployment."""
import argparse
import http.server
import mimetypes
from pathlib import Path
import sys
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / 'builders/ansible/roles/observability-stack'
sys.path.insert(0, str(ROLE / 'files'))
from homepage_api import Handler, HomepageData


class Preview(Handler):
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path.startswith('/api/'):
            return super().do_GET()
        path = path.lstrip('/') or 'index.html'
        for directory in (ROLE / 'templates/homepage', ROLE / 'files/homepage'):
            candidate = (directory / path).resolve()
            if candidate.is_relative_to(directory.resolve()) and candidate.is_file():
                body = candidate.read_bytes()
                if path == 'index.html':
                    body += b'<script>if(innerWidth>900)requestAnimationFrame(() => window.scrollTo(0, document.documentElement.scrollHeight));</script>'
                self.send_response(200)
                self.send_header('Content-Type', mimetypes.guess_type(path)[0] or 'application/octet-stream')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)
                return
        self.send_error(404)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', type=int, default=8766)
    p.add_argument('--status', default='http://jwst:8080/status.json')
    p.add_argument('--prometheus', default='http://jwst:9090')
    p.add_argument('--loki', default='http://jwst:3100')
    args = p.parse_args()
    server = http.server.ThreadingHTTPServer(('127.0.0.1', args.port), Preview)
    server.data = HomepageData(args.status, args.prometheus, args.loki)
    print(f'Local preview: http://127.0.0.1:{args.port}/index.html#architecture', flush=True)
    server.serve_forever()
