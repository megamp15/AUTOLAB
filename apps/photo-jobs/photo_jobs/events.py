"""Looking inside an event folder before it is filed: every photo, the date it carries and where
that date came from, so a month the sorter chose can be checked against what the folder says."""
import collections
import json
import os
import re
import subprocess
import time

from . import core
from . import previews

_cache = {}          # folder -> (when, rows): reading a few thousand photos off the NAS takes a while
_TTL = 120
STAMP = re.compile(r'^(19[7-9]\d|20\d\d)-(0[1-9]|1[0-2])-')


def _read(paths):
    """[(path, 'YYYY-MM-DD HH:MM:SS' or '', tag or '')] using the tags the sorter reads, in its order."""
    out = {}
    for i in range(0, len(paths), 500):
        try:
            res = subprocess.run(['exiftool', '-json', '-api', 'QuickTimeUTC', '-d', '%Y-%m-%d %H:%M:%S',
                                  *[f'-{t}' for t in core.DATE_TAGS], *paths[i:i + 500]],
                                 capture_output=True, text=True, timeout=300).stdout
            rows = json.loads(res or '[]')
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            rows = []
        for r in rows:
            for tag in core.DATE_TAGS:
                v = str(r.get(tag, ''))
                if STAMP.match(v):
                    out[r['SourceFile']] = (v, tag)
                    break
    return [(p, *out.get(p, ('', ''))) for p in paths]


def _rows(cfg, rel):
    hit = _cache.get(rel)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    folder = cfg.abs(rel)
    paths = sorted(p for p in core.files_under(folder) if core.is_media(p))
    rows = []
    for p, taken, tag in _read(paths):
        try:
            mod = os.stat(p).st_mtime
        except OSError:
            continue
        rows.append({'path': cfg.rel(p), 'name': os.path.basename(p), 'taken': taken, 'source': tag,
                     'modified': mod, 'video': previews.is_video(p)})
    rows.sort(key=lambda r: (not r['taken'], r['taken'], r['path']))
    _cache[rel] = (time.time(), rows)
    return rows


def inspect(cfg, rel, month='', offset=0, limit=100):
    """What is inside the folder `rel`: a page of its photos and a summary by month. `month` is
    'YYYY-MM', or 'none' for photos with no date, or '' for all."""
    if not os.path.isdir(cfg.abs(rel)):
        raise ValueError('not a folder')
    rows = _rows(cfg, rel)
    months = collections.Counter(r['taken'][:7] or 'none' for r in rows)
    changed = collections.Counter(time.strftime('%Y-%m', time.localtime(r['modified'])) for r in rows)
    named = core.NAMED.match(os.path.basename(rel))
    shown = [r for r in rows if not month or (r['taken'][:7] or 'none') == month]
    return {'folder': rel, 'total': len(rows), 'months': dict(sorted(months.items())),
            'changed': dict(sorted(changed.items())), 'name_says': '-'.join(named.groups()) if named else '',
            'matching': len(shown), 'offset': offset, 'files': shown[offset:offset + limit]}
