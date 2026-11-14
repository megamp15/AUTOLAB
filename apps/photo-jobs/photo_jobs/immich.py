"""Small client for Immich's external-library assets, albums, and trash."""
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
                if r.status == 204:
                    return None
                return json.load(r)
        except urllib.error.HTTPError as e:
            raise ImmichError(f'Immich answered {e.code} for {path}: {e.read(300).decode(errors="replace")}') from None
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            raise ImmichError(f'cannot reach Immich at {self.url}: {e}') from None

    def check(self):
        """Whether the key works, using only a permission the workflows already need (asset.read).
        Who it belongs to and the version are added when the key's permissions allow them."""
        self.call('POST', '/search/metadata', {'size': 1, 'page': 1})
        info = {'user': '', 'version': ''}
        try:
            me = self.call('GET', '/users/me')
            info['user'] = me.get('email') or me.get('name') or ''
        except ImmichError:
            pass
        try:
            info['version'] = self.call('GET', '/server/about').get('version', '')
        except ImmichError:
            pass
        return info

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
        """Walk a metadata search. Immich 3.x pages a `filter` search with a cursor and refuses
        `page` beside it; the older body (withDeleted) is paged by number."""
        cursor, page, seen = None, 1, 0
        while True:
            req = {**body, 'size': PAGE}
            if 'filter' in body:
                if cursor:
                    req['cursor'] = cursor
            else:
                req['page'] = page
            assets = self.call('POST', '/search/metadata', req).get('assets', {})
            items = assets.get('items', [])
            for a in items:
                if a.get('isTrashed'):
                    yield a
            seen += len(items)
            progress(seen, assets.get('total') or 0, 'reading Immich’s trash')
            cursor, nxt = assets.get('nextCursor'), assets.get('nextPage')
            if 'filter' in body:
                if not cursor:
                    return
            elif nxt:
                page = int(nxt)
            else:
                return

    def asset(self, id_):
        return self.call('GET', f'/assets/{id_}')

    def search_assets(self, filters):
        """Return all non-trashed assets matching an Immich metadata filter."""
        found, cursor = [], None
        while True:
            body = {'filter': filters, 'size': PAGE, **({'cursor': cursor} if cursor else {})}
            assets = self.call('POST', '/search/metadata', body).get('assets', {})
            found.extend(a for a in assets.get('items', []) if not a.get('isTrashed'))
            cursor = assets.get('nextCursor')
            if not cursor:
                return found

    def albums(self):
        return self.call('GET', '/albums')

    def libraries(self):
        return self.call('GET', '/libraries')

    def scan_library(self, library_id):
        """Queue an external-library scan. Immich processes it asynchronously."""
        return self.call('POST', f'/libraries/{library_id}/scan')

    def album_assets(self, album_id):
        return self.search_assets({'albumIds': {'in': [album_id]}})

    def create_album(self, name, asset_ids):
        return self.call('POST', '/albums', {'albumName': name, 'assetIds': asset_ids})

    def add_album_assets(self, album_id, asset_ids):
        return self.call('PUT', f'/albums/{album_id}/assets', {'assetIds': asset_ids})


def checksum_hex(b64):
    """Immich stores a file's SHA-1 as base64; the file's hex digest is what we can compute."""
    try:
        return base64.b64decode(b64).hex()
    except (ValueError, TypeError):
        return ''
