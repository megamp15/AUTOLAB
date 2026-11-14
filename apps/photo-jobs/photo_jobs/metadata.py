"""Finding photos anywhere in the media folder and editing what is stored inside them: when it was
taken, where, and a description.

Immich reads the media folder read-only, so an edit made in Immich lives only in its database and a
rescan undoes it. The edit that lasts is in the file itself (and in its .xmp sidecar, which Immich
trusts over the photo). Every edit records the values it replaced, so it can be undone.
"""
import json
import os
import re
import subprocess
import threading
import time

from . import core, nodate, previews

LISTING_TTL = 60
MAX_FILES = 500
_listing, _lock = {'at': 0.0, 'files': []}, threading.Lock()
FLOAT = re.compile(r'[-+]?\d+(?:\.\d+)?')


# ----------------------------------------------------------------------------------------------
# Finding
# ----------------------------------------------------------------------------------------------
def _all_media(cfg):
    """Every photo and video under the media folder, kept for a minute so typing in the search box does not walk the disk."""
    with _lock:
        if time.time() - _listing['at'] > LISTING_TTL or _listing.get('root') != cfg.root:
            files = []
            for p in core.files_under(cfg.root):
                if core.is_media(p):
                    files.append(cfg.rel(p))
            _listing.update(at=time.time(), root=cfg.root, files=files)
        return _listing['files']


def forget_listing():
    _listing['at'] = 0.0


def find(cfg, q='', folder='', kind='', offset=0, limit=60):
    """Files whose path contains every word of `q`, optionally inside one top-level folder, and only
    photos or only videos. Newest path last: a stable, readable order."""
    words = [w for w in q.lower().split() if w]
    folder = folder.strip('/')
    rows = []
    for rel in _all_media(cfg):
        low = rel.lower()
        if folder and not (rel == folder or rel.startswith(folder + '/')):
            continue
        if kind == 'video' and not previews.is_video(rel):
            continue
        if kind == 'photo' and previews.is_video(rel):
            continue
        if all(w in low for w in words):
            rows.append(rel)
    total = len(rows)
    out = []
    for rel in rows[offset:offset + limit]:
        try:
            st = os.stat(cfg.abs(rel))
        except OSError:
            continue
        out.append({'path': rel, 'name': os.path.basename(rel), 'size': st.st_size, 'modified': st.st_mtime,
                    'video': previews.is_video(rel)})
    return {'total': total, 'files': out}


def top_folders(cfg):
    """The folders directly inside the media folder, for the search's folder filter."""
    try:
        return sorted(n for n in os.listdir(cfg.root) if os.path.isdir(os.path.join(cfg.root, n)) and n not in core.SKIP)
    except OSError:
        return []


# ----------------------------------------------------------------------------------------------
# Reading
# ----------------------------------------------------------------------------------------------
READ_TAGS = ['DateTimeOriginal', 'CreateDate', 'ModifyDate', 'MediaCreateDate', 'GPSLatitude', 'GPSLongitude',
             'GPSAltitude', 'GPSCoordinates', 'ImageDescription', 'Description', 'Make', 'Model', 'ImageWidth', 'ImageHeight']


def _moment(raw):
    """'2025:06:14 12:00:00+02:00' -> '2025-06-14 12:00:00'; anything unreadable -> ''."""
    m = re.match(r'^((?:19|20)\d\d)[:\-](\d\d)[:\-](\d\d)(?:[ T](\d\d):(\d\d):?(\d\d)?)?', str(raw or ''))
    if not m:
        return ''
    y, mo, d, h, mi, s = m.groups()
    return f'{y}-{mo}-{d} {h or "12"}:{mi or "00"}:{s or "00"}'


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read(cfg, rels):
    """What each file says about itself: {'path', 'taken', 'lat', 'lon', 'alt', 'description', 'camera', 'width', 'height'}."""
    paths = [cfg.abs(r) for r in rels]
    out = {}
    for i in range(0, len(paths), 200):
        try:
            res = subprocess.run(['exiftool', '-json', '-n', '-api', 'QuickTimeUTC', *[f'-{t}' for t in READ_TAGS], *paths[i:i + 200]],
                                 capture_output=True, text=True, timeout=300).stdout
            items = json.loads(res or '[]')
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            items = []
        for it in items:
            out[it['SourceFile']] = it
    rows = []
    for rel, path in zip(rels, paths):
        it = out.get(path, {})
        lat, lon, alt = _number(it.get('GPSLatitude')), _number(it.get('GPSLongitude')), _number(it.get('GPSAltitude'))
        if lat is None or lon is None:                      # a video keeps it as one string
            nums = FLOAT.findall(str(it.get('GPSCoordinates', '')))
            lat, lon = (float(nums[0]), float(nums[1])) if len(nums) >= 2 else (None, None)
        rows.append({'path': rel, 'taken': next((_moment(it[t]) for t in ('DateTimeOriginal', 'CreateDate', 'MediaCreateDate') if _moment(it.get(t))), ''),
                     'lat': lat, 'lon': lon, 'alt': alt,
                     'description': str(it.get('ImageDescription') or it.get('Description') or ''),
                     'camera': ' '.join(str(it[t]) for t in ('Make', 'Model') if it.get(t)),
                     'width': it.get('ImageWidth'), 'height': it.get('ImageHeight'),
                     'raw': {t: it.get(t) for t in ('DateTimeOriginal', 'CreateDate', 'ModifyDate')}})
    return rows


def parse_location(text):
    """'30.6280, -96.3344' (as Google Maps and most phones copy it) -> (30.628, -96.3344)."""
    nums = FLOAT.findall(str(text))
    if len(nums) < 2:
        raise ValueError('give the location as two numbers, latitude then longitude, like 30.6280, -96.3344')
    lat, lon = float(nums[0]), float(nums[1])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('latitude must be between -90 and 90 and longitude between -180 and 180')
    return lat, lon


# ----------------------------------------------------------------------------------------------
# Writing
# ----------------------------------------------------------------------------------------------
def sidecars(path):
    """The .xmp files that belong to a photo (IMG_1.HEIC.xmp or IMG_1.xmp), when they exist."""
    return [c for c in (path + '.xmp', os.path.splitext(path)[0] + '.xmp') if os.path.isfile(c)]


def _args(change, video, sidecar=False):
    args = []
    if change.get('when'):
        args.append(f'-AllDates={change["when"]}')
        if video and not sidecar:
            args += [f'-MediaCreateDate={change["when"]}', f'-TrackCreateDate={change["when"]}']
    if change.get('lat') is not None:
        lat, lon = change['lat'], change['lon']
        if sidecar:
            args += [f'-XMP:GPSLatitude={lat}', f'-XMP:GPSLongitude={lon}']
        else:
            args += [f'-GPSLatitude={abs(lat)}', f'-GPSLatitudeRef={"N" if lat >= 0 else "S"}',
                     f'-GPSLongitude={abs(lon)}', f'-GPSLongitudeRef={"E" if lon >= 0 else "W"}']
            if video:
                args.append(f'-GPSCoordinates={lat}, {lon}')
    if change.get('clear_location'):
        args += ['-GPSLatitude=', '-GPSLongitude=', '-GPSLatitudeRef=', '-GPSLongitudeRef=', '-GPSAltitude=', '-GPSCoordinates=']
    if change.get('description') is not None:
        args += [f'-XMP-dc:Description={change["description"]}'] + ([] if sidecar else [f'-ImageDescription={change["description"]}'])
    return args


def _run(path, args):
    try:
        done = subprocess.run(['exiftool', '-overwrite_original', '-api', 'QuickTimeUTC', *args, path],
                              capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        return 'ExifTool is not installed'
    except subprocess.TimeoutExpired:
        return 'ExifTool took too long'
    if done.returncode != 0:
        said = (done.stderr or done.stdout).strip()
        return said.splitlines()[-1][:200] if said else 'ExifTool failed'
    return ''


def write(cfg, rel, change):
    """Write a change into the file and its sidecars, then read it back to be sure it took.
    '' when it did, else why not."""
    path = cfg.abs(rel)
    if not os.path.isfile(path):
        return 'the file is no longer there'
    args = _args(change, previews.is_video(path))
    if args:
        why = _run(path, args)
        if why:
            return why
        for side in sidecars(path):                 # Immich trusts a sidecar over the photo
            why = _run(side, _args(change, False, sidecar=True))
            if why:
                return 'the photo was changed but its sidecar was not: ' + why
    now = read(cfg, [rel])[0]
    if change.get('when') and not now['taken'].startswith(change['when'][:10].replace(':', '-')):
        return 'this file type cannot hold a date'
    if change.get('lat') is not None and (now['lat'] is None or abs(now['lat'] - change['lat']) > 1e-3 or abs(now['lon'] - change['lon']) > 1e-3):
        return 'this file type cannot hold a location'
    if change.get('description') and change['description'] not in now['description']:
        return 'this file type cannot hold a description'
    return ''


def _snapshot(row):
    return {'DateTimeOriginal': row['raw'].get('DateTimeOriginal'), 'CreateDate': row['raw'].get('CreateDate'),
            'ModifyDate': row['raw'].get('ModifyDate'), 'lat': row['lat'], 'lon': row['lon'], 'alt': row['alt'],
            'description': row['description']}


def _restore_args(before, sidecar, video=False):
    args = [f'-{tag}={before.get(tag) or ""}' for tag in ('DateTimeOriginal', 'CreateDate', 'ModifyDate')]
    lat, lon = before.get('lat'), before.get('lon')
    if lat is not None and lon is not None:
        args += ([f'-XMP:GPSLatitude={lat}', f'-XMP:GPSLongitude={lon}'] if sidecar else
                 [f'-GPSLatitude={abs(lat)}', f'-GPSLatitudeRef={"N" if lat >= 0 else "S"}',
                  f'-GPSLongitude={abs(lon)}', f'-GPSLongitudeRef={"E" if lon >= 0 else "W"}']
                 + ([f'-GPSCoordinates={lat}, {lon}'] if video else []))     # a video keeps its location in another tag
    else:
        args += ['-GPSLatitude=', '-GPSLongitude=', '-GPSLatitudeRef=', '-GPSLongitudeRef=', '-GPSAltitude=', '-GPSCoordinates=']
    desc = before.get('description') or ''
    return args + [f'-XMP-dc:Description={desc}'] + ([] if sidecar else [f'-ImageDescription={desc}'])


def restore(cfg, rel, before):
    """Put back what a file (and its sidecars) said before an edit. A value that was not there is removed again."""
    path = cfg.abs(rel)
    if not os.path.isfile(path):
        return 'the file is no longer there'
    why = _run(path, _restore_args(before, False, previews.is_video(path)))
    for side in sidecars(path):
        why = why or _run(side, _restore_args(before, True))
    return why


def edit(cfg, rels, spec, progress=core._noop, record=None):
    """Apply `spec` to each file: {'day': 'YYYY-MM-DD'?, 'time': 'HH:MM'?, 'day_only': bool, 'lat', 'lon', 'description'}.
    With day_only each file keeps its own time of day (12:00 if it had none). Returns a run."""
    run = {'started': time.time(), 'finished': None, 'moves': [], 'undone': None, 'spec': {k: v for k, v in spec.items() if k != 'ref'}}
    for i, rel in enumerate(rels, 1):
        entry = {'src': rel, 'dst': '', 'kind': 'metadata', 'status': 'edited', 'note': ''}
        try:
            before = read(cfg, [rel])[0]
            change = {}
            if spec.get('day'):
                own = before['taken'][11:16] if before['taken'] else ''
                clock = (spec.get('time') if not spec.get('day_only') else own or spec.get('time')) or '12:00'
                change['when'] = nodate.stamp(spec['day'], clock)
            if spec.get('lat') is not None:
                change.update(lat=spec['lat'], lon=spec['lon'])
            if spec.get('description') is not None:
                change['description'] = spec['description']
            entry['before'] = _snapshot(before)
            why = write(cfg, rel, change)
            if why:
                entry.update(status='error', note=why)
                restore(cfg, rel, entry['before'])        # leave the file as it was
        except (OSError, ValueError) as e:
            entry.update(status='error', note=str(e))
        run['moves'].append(entry)
        progress(i, len(rels), 'writing metadata')
        if record and i % 25 == 0:
            record(run)
    run['finished'] = time.time()
    forget_listing()
    if record:
        record(run)
    return run


def undo(cfg, run, progress=core._noop):
    done = [m for m in run['moves'] if m['status'] == 'edited']
    result = {'restored': 0, 'skipped': [], 'not_restorable': 0}
    for i, m in enumerate(reversed(done), 1):
        why = restore(cfg, m['src'], m['before'])
        if why:
            result['skipped'].append({'path': m['src'], 'note': why})
        else:
            result['restored'] += 1
        progress(i, len(done), 'restoring')
    return result
