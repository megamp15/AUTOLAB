"""A small client for the one thing Photo Jobs asks Immich: which assets are in its trash.

Immich never deletes the files of an external library; trashing an asset only hides it. This
reads the trash so the files can be reviewed and removed here. It needs an API key with the
`asset.read` permission and changes nothing in Immich.
"""
import base64
import json
import urllib.error
import urllib.request

PAGE = 500


class ImmichError(Exception):
    pass


class Immich:
    def __init__(self, url, key, timeout=30):
        self.url, self.key, self.timeout = url.rstrip('/'), key, timeout

    @property
    def configured(self):
        return bool(self.url and self.key)

    def call(self, method, path, body=None):
        req = urllib.request.Request(
            f'{self.url}/api{path}', method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'x-api-key': self.key, 'Accept': 'application/json', 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            raise ImmichError(f'Immich answered {e.code} for {path}: {e.read(300).decode(errors="replace")}') from None
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            raise ImmichError(f'cannot reach Immich at {self.url}: {e}') from None

    def check(self):
        """Who the key belongs to and what Immich version this is."""
        me = self.call('GET', '/users/me')
        try:
            version = self.call('GET', '/server/about').get('version', '')
        except ImmichError:
            version = ''
        return {'user': me.get('email') or me.get('name') or '', 'version': version}

    def trashed(self, progress=lambda *a, **k: None):
        """Every asset in the trash. The current search takes a trashedAt filter; older servers
        take withDeleted. Whichever the server accepts, only assets Immich says are trashed are kept."""
        for body in ({'filter': {'trashedAt': {'ne': None}}}, {'withDeleted': True, 'trashedAfter': '1970-01-01T00:00:00.000Z'}):
            try:
                return list(self._pages(body, progress))
            except ImmichError as e:
                last = e
                if ' 400 ' not in str(e):
                    raise
        raise last

    def _pages(self, body, progress):
        page, seen = 1, 0
        while page:
            res = self.call('POST', '/search/metadata', {**body, 'size': PAGE, 'page': page})
            items = res.get('assets', {}).get('items', [])
            for a in items:
                if a.get('isTrashed'):
                    yield a
            seen += len(items)
            progress(seen, res.get('assets', {}).get('total') or 0, 'reading Immich’s trash')
            page = int(res['assets']['nextPage']) if res.get('assets', {}).get('nextPage') else 0

    def asset(self, id_):
        return self.call('GET', f'/assets/{id_}')


def checksum_hex(b64):
    """Immich stores a file's SHA-1 as base64; the file's hex digest is what we can compute."""
    try:
        return base64.b64decode(b64).hex()
    except (ValueError, TypeError):
        return ''
