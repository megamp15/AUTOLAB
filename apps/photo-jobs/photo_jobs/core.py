"""Planning, applying and undoing photo-library moves.

Three steps, kept apart on purpose:

  plan   reads the library and returns the exact moves it would make. Changes nothing.
  apply  makes the moves in a plan that were not unticked, and writes a run record.
  undo   puts a run's moves back.

Apply never re-plans: it does what the reviewed plan says, and skips any move whose source is
gone or whose destination now exists. Nothing here deletes a photo; "duplicates" are filed under
_duplicates/ beside the copy that is kept.

Where things are put decides what happens to them; names do not matter:
  _inbox/loose/          every photo and video is sorted on its own into library/YYYY/MM/
  _inbox/events/         each folder is one event and moves whole into library/YYYY/MM/<folder>:
                         the month most of its photos are from, or the month before that if it has
                         at least half as many (the event started there)
  library/YYYY/<folder>  a folder directly in a year folder (not a month) is an event too
A Live Photo's still and clip (see pairs.py) are dated, named and filed as one.
"""
import collections
import hashlib
import json
import os
import re
import subprocess
import time

from . import immich as immich_api
from . import pairs as live_photos

MEDIA = {'.jpg', '.jpeg', '.heic', '.heif', '.png', '.gif', '.webp', '.tif', '.tiff', '.dng',
         '.raw', '.cr2', '.cr3', '.nef', '.arw', '.orf', '.rw2', '.mov', '.mp4', '.m4v',
         '.avi', '.mkv', '.3gp', '.mts', '.m2ts'}
DATE_TAGS = ['DateTimeOriginal', 'SubSecDateTimeOriginal', 'CreationDate', 'CreateDate',
             'MediaCreateDate', 'TrackCreateDate', 'ContentCreateDate']
SKIP = {'@eaDir', '#recycle', '#snapshot', '.DS_Store', 'Thumbs.db', '.stversions', '.stfolder'}
JUNK = {'.DS_Store', 'Thumbs.db', 'desktop.ini'}
YEAR = re.compile(r'^\d{4}$')
MONTH = re.compile(r'^(0[1-9]|1[0-2])$')
NAMED = re.compile(r'^((?:19|20)\d\d)[_-](0[1-9]|1[0-2])[_-]')
NODATE, DUPS, REMOVED = '_no_date', '_duplicates', '_removed'
LOOSE, EVENTS = ('_inbox', 'loose'), ('_inbox', 'events')


class Config:
    def __init__(self, root, state, library='library', immich_prefix='/mnt/mahir-personal'):
        self.root = os.path.abspath(root)
        self.state = os.path.abspath(state)
        self.library = library
        # Where the media folder appears inside Immich's container: an asset's originalPath
        # starts with this when its file is in this library.
        self.immich_prefix = immich_prefix.rstrip('/')

    @property
    def lib(self):
        return os.path.join(self.root, self.library)

    def rel(self, path):
        return os.path.relpath(path, self.root)

    def abs(self, rel):
        path = os.path.normpath(os.path.join(self.root, rel))
        if path != self.root and not path.startswith(self.root + os.sep):
            raise ValueError(f'outside the media folder: {rel}')
        return path


def _noop(done=None, total=None, message=None):
    pass


def files_under(base):
    for d, ds, fs in os.walk(base):
        ds[:] = sorted(x for x in ds if x not in SKIP)
        for f in sorted(fs):
            if f not in SKIP and not f.startswith('._'):
                yield os.path.join(d, f)


def is_media(path):
    return os.path.splitext(path)[1].lower() in MEDIA


def recording_months(paths, progress=_noop):
    """{path: 'YYYY-MM'} for the files ExifTool can date."""
    out = {}
    for i in range(0, len(paths), 500):
        res = subprocess.run(['exiftool', '-json', '-api', 'QuickTimeUTC', '-d', '%Y-%m',
                              *[f'-{t}' for t in DATE_TAGS], *paths[i:i + 500]],
                             capture_output=True, text=True).stdout
        for r in json.loads(res or '[]'):
            for t in DATE_TAGS:
                v = str(r.get(t, ''))
                if re.match(r'^(19[7-9]\d|20\d\d)-(0[1-9]|1[0-2])$', v):
                    out[r['SourceFile']] = v
                    break
        progress(min(i + 500, len(paths)), len(paths), 'reading recording dates')
    return out


def prune_empty(cfg, remove):
    """Folders left with nothing in them (or only .DS_Store, ._*, Thumbs.db). remove=False only
    counts them. Never media itself, the library root or the inbox."""
    keep = {cfg.root, cfg.lib, os.path.join(cfg.root, '_inbox'),
            os.path.join(cfg.root, *LOOSE), os.path.join(cfg.root, *EVENTS)}
    gone = []
    for d, _, _ in os.walk(cfg.root, topdown=False):
        if d in keep or os.path.basename(d) in SKIP:
            continue
        names = [n for n in os.listdir(d) if os.path.join(d, n) not in gone]
        if all(n in JUNK or n.startswith('._') for n in names):
            if remove:
                for n in names:
                    os.remove(os.path.join(d, n))
                os.rmdir(d)
            gone.append(d)
    return gone


# ----------------------------------------------------------------------------------------------
# Sorting the inbox
# ----------------------------------------------------------------------------------------------
class SortPlanner:
    def __init__(self, cfg, progress=_noop):
        self.cfg, self.progress = cfg, progress
        self.moves, self.notes, self.taken, self.hashes = [], [], set(), {}
        self.alias = {}   # a planned destination -> the file that will be moved there
        self.sizes = collections.defaultdict(list)   # every sorted file, by size, for duplicates
        self.pairs = 0
        years = [os.path.join(cfg.lib, y) for y in (os.listdir(cfg.lib) if os.path.isdir(cfg.lib) else [])
                 if YEAR.match(y)]
        for base in years + [os.path.join(cfg.root, NODATE)]:
            if os.path.isdir(base):
                for p in files_under(base):
                    self.sizes[os.path.getsize(p)].append(p)

    # -- helpers
    def sha1(self, p):
        if p in self.alias:   # planned, not there yet: it is a copy of the file that will be moved there
            return self.sha1(self.alias[p])
        if p not in self.hashes:
            h = hashlib.sha1()
            with open(p, 'rb') as f:
                for b in iter(lambda: f.read(1 << 20), b''):
                    h.update(b)
            self.hashes[p] = h.hexdigest()
        return self.hashes[p]

    def duplicate_of(self, p, ignore=''):
        return next((q for q in self.sizes[os.path.getsize(p)]
                     if q != p and not q.startswith(ignore or '\0') and self.sha1(q) == self.sha1(p)), None)

    def free(self, path):
        b, e = os.path.splitext(path)
        n, c = 1, path
        while c.lower() in self.taken or os.path.lexists(c):
            c = f'{b}_{n}{e}'
            n += 1
        self.taken.add(c.lower())
        return c

    def free_set(self, folder, stem, exts):
        """Names for a still and its clip that are free for every one of them, with the same _N
        suffix: IMG_1.HEIC clashing must send IMG_1.MOV to IMG_1_1.MOV too, not leave it behind."""
        n = 0
        while True:
            names = [os.path.join(folder, f'{stem}{"_%d" % n if n else ""}{e}') for e in exts]
            if not any(c.lower() in self.taken or os.path.lexists(c) for c in names):
                self.taken.update(c.lower() for c in names)
                return names
            n += 1

    def move(self, src, dst, why, kind, group=None):
        self.moves.append({'id': len(self.moves), 'src': self.cfg.rel(src), 'dst': self.cfg.rel(dst),
                           'why': why, 'kind': kind, 'group': group})

    def remember(self, planned, source):
        """Later files in this run count `source` as sorted, at the path it will have."""
        self.alias[planned] = source
        self.sizes[os.path.getsize(source)].append(planned)

    def drop_duplicate(self, p, dup, group=None):
        """A copy of dup, which is already sorted: file it under _duplicates/, beside its copy."""
        home = self.cfg.lib if dup.startswith(self.cfg.lib + '/') else self.cfg.root
        dest = self.free(os.path.join(self.cfg.root, DUPS, os.path.relpath(os.path.dirname(dup), home),
                                      os.path.basename(p)))
        self.move(p, dest, f'copy of {self.cfg.rel(dup)}', 'duplicate', group)
        return dest

    # -- the loose inbox
    def sort_loose(self, files):
        media = [p for p in files if is_media(p)]
        side = {p for p in files if p.lower().endswith('.xmp')}
        months = recording_months(media, self.progress)
        clip_of = live_photos.pairs(media)                 # clip -> still
        clips = {still: clip for clip, still in clip_of.items()}
        for p in media:
            if p in clip_of:
                continue   # sorted together with its still
            members = [p] + ([clips[p]] if p in clips else [])
            group = f'pair:{self.cfg.rel(p)}' if len(members) > 1 else None
            self.pairs += len(members) > 1
            dups = [self.duplicate_of(m) for m in members]
            if all(dups):   # every half is already sorted: each is filed beside its copy
                dests = [self.drop_duplicate(m, d, group) for m, d in zip(members, dups)]
            else:   # new, or a pair with a half that is new: the pair is never split
                month = months.get(p) or next((months[m] for m in members if m in months), None)
                if len(members) == 1:
                    if month:
                        y, mo = month.split('-')
                        dests, why, kind = ([self.free(os.path.join(self.cfg.lib, y, mo, os.path.basename(p)))],
                                            f'recorded {month}', 'sorted')
                    else:
                        dests, why, kind = ([self.free(os.path.join(self.cfg.root, NODATE, self.cfg.rel(p)))],
                                            'no recording time', 'no date')
                else:
                    stem = os.path.splitext(os.path.basename(p))[0]
                    exts = [os.path.splitext(m)[1] for m in members]
                    if month:
                        y, mo = month.split('-')
                        folder, why, kind = os.path.join(self.cfg.lib, y, mo), f'recorded {month}', 'sorted'
                    else:
                        folder = os.path.join(self.cfg.root, NODATE, self.cfg.rel(os.path.dirname(p)))
                        why, kind = 'no recording time', 'no date'
                    dests = self.free_set(folder, stem, exts)
                    why += f'; Live Photo with {os.path.basename(members[1])}'
                for m, dest in zip(members, dests):
                    self.move(m, dest, why, kind, group)
                for m, dest in zip(members, dests):
                    self.remember(dest, m)
            for m, dest in zip(members, dests):
                for sc in (m + '.xmp', os.path.splitext(m)[0] + '.xmp'):
                    if sc in side:
                        side.discard(sc)
                        self.move(sc, self.free(dest + '.xmp'), 'sidecar of ' + os.path.basename(m), 'sidecar', group)
        return [p for p in files if not is_media(p) and (not p.lower().endswith('.xmp') or p in side)]

    # -- events
    def place_event(self, folder):
        files = list(files_under(folder))
        media = [p for p in files if is_media(p)]
        months = recording_months(media, self.progress)
        if not months:
            self.notes.append(f'event has no dated photos, left where it is: {self.cfg.rel(folder)}')
            return files
        spread = collections.Counter(months.values())
        # The month most of its photos are from, so a few strays cannot carry the event off.
        # If the month just before has at least half as many, the event started there: a trip
        # from the 28th to the 5th belongs to the first month.
        top, count = spread.most_common(1)[0]
        ty, tm = map(int, top.split('-'))
        before = f'{ty - (tm == 1)}-{12 if tm == 1 else tm - 1:02d}'
        chosen = before if spread.get(before, 0) * 2 >= count else top
        y, m = chosen.split('-')
        by = 'started the month before' if chosen == before else 'most photos'
        named = NAMED.match(os.path.basename(folder))
        if named and '-'.join(named.groups()) != chosen:
            by += f'; CHECK: name says {"-".join(named.groups())}'
        mix = ', '.join(f'{k}:{v}' for k, v in sorted(spread.items()))
        dest = os.path.join(self.cfg.lib, y, m, os.path.basename(folder))
        if os.path.abspath(folder) == os.path.abspath(dest):
            return []
        group = f'event:{self.cfg.rel(folder)}'
        if not os.path.lexists(dest) and dest.lower() not in self.taken:
            self.taken.add(dest.lower())
            self.move(folder, dest, f'event {y}-{m} by {by} ({len(media)} photos; {mix})', 'event', group)
            return []
        # same event already in its month: merge file by file
        clip_of = live_photos.pairs(media)
        clips = {still: clip for clip, still in clip_of.items()}
        for p in files:
            if p in clip_of:
                continue   # merged together with its still
            members = [p] + ([clips[p]] if p in clips else [])
            dups = [self.duplicate_of(m, ignore=folder + '/') if is_media(m) else None for m in members]
            if all(dups):
                for m, d in zip(members, dups):
                    self.drop_duplicate(m, d, group)
                continue
            why = f'merged into {self.cfg.rel(dest)}'
            target = os.path.join(dest, os.path.relpath(p, folder))
            if len(members) == 1:
                self.move(p, self.free(target), why, 'merged', group)
            else:
                stem = os.path.splitext(os.path.basename(target))[0]
                names = self.free_set(os.path.dirname(target), stem, [os.path.splitext(m)[1] for m in members])
                for m, name in zip(members, names):
                    self.move(m, name, why + '; Live Photo', 'merged', group)
        return []

    def run(self):
        cfg = self.cfg
        stray = sorted(y for y in os.listdir(cfg.root) if YEAR.match(y) and os.path.isdir(os.path.join(cfg.root, y)))
        if stray:
            self.notes.append(f'year folders outside {cfg.library}/: {", ".join(stray)}; move them into it')
        loose_dir, events_dir = os.path.join(cfg.root, *LOOSE), os.path.join(cfg.root, *EVENTS)
        left = []
        if os.path.isdir(loose_dir):
            left += self.sort_loose(list(files_under(loose_dir)))
        if os.path.isdir(events_dir):
            for name in sorted(os.listdir(events_dir)):
                p = os.path.join(events_dir, name)
                if os.path.isdir(p) and name not in SKIP:
                    left += self.place_event(p)
                elif os.path.isfile(p) and not name.startswith('.'):
                    left.append(p)
        for y in sorted(os.listdir(cfg.lib) if os.path.isdir(cfg.lib) else []):
            yp = os.path.join(cfg.lib, y)
            if YEAR.match(y) and os.path.isdir(yp):
                for name in sorted(os.listdir(yp)):
                    p = os.path.join(yp, name)
                    if os.path.isdir(p) and not MONTH.match(name) and name not in SKIP:
                        left += self.place_event(p)
        return left


def plan_sort(cfg, progress=_noop):
    """What sorting the inbox (and year-level event folders) would do."""
    planner = SortPlanner(cfg, progress)
    progress(0, 0, 'looking through the inbox')
    left = planner.run()
    kinds = collections.Counter(m['kind'] for m in planner.moves)
    return {'kind': 'sort', 'moves': planner.moves, 'left': [cfg.rel(p) for p in left],
            'notes': planner.notes,
            'stats': {'moves': len(planner.moves), 'kinds': dict(kinds), 'pairs': planner.pairs,
                      'left': len(left), 'empty_folders': len(prune_empty(cfg, False))}}


# ----------------------------------------------------------------------------------------------
# Byte-identical duplicates
# ----------------------------------------------------------------------------------------------
def _in_library(cfg, rel):
    """library/2025/06/x -> 2025/06/x; anything else unchanged"""
    return rel.split('/', 1)[1] if rel.startswith(cfg.library + '/') else rel


def _rank(cfg, rel):
    """Lower is a better copy to keep."""
    parts = _in_library(cfg, rel).split('/')
    top = parts[0]
    if YEAR.match(top) and len(parts) >= 4 and MONTH.match(parts[1]):
        place = 0                       # inside an event folder in a month
    elif YEAR.match(top) and len(parts) == 3 and MONTH.match(parts[1]):
        place = 1                       # loose in a month folder
    elif top == NODATE:
        place = 3
    elif top == '_inbox':
        place = 4
    elif top == DUPS:
        place = 5
    else:
        place = 2
    name = parts[-1]
    # an ID name from the old Immich (2ae8dca5-6443-...) loses to the real one (IMG_8005.MOV)
    id_name = bool(re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-', name, re.I))
    # a clash suffix is _1, _2 added after a name that already ends in a number (IMG_8005_1)
    suffixed = bool(re.search(r'\d_\d{1,2}\.[^.]+$', name)) or bool(re.search(r' copy|\(\d+\)', name, re.I))
    return (place, id_name, suffixed, len(rel), rel)


def _digest(path, limit=None):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        if limit:
            h.update(f.read(limit))
        else:
            for b in iter(lambda: f.read(1 << 20), b''):
                h.update(b)
    return h.hexdigest()


def plan_duplicates(cfg, progress=_noop):
    """Groups of byte-identical photos and videos across the whole media folder, best copy first.
    Sidecars are left out: those of different photos are often identical, each belongs to its own."""
    by_size, n = collections.defaultdict(list), 0
    for d, ds, fs in os.walk(cfg.root):
        ds[:] = sorted(x for x in ds if x not in SKIP)
        for f in fs:
            if f in SKIP or f.startswith('._') or not is_media(f):
                continue
            p = os.path.join(d, f)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            if size:
                by_size[size].append(p)
                n += 1
    candidates = [ps for ps in by_size.values() if len(ps) > 1]
    total, done, found = sum(map(len, candidates)), 0, []
    progress(0, total, f'{n} files; comparing the {total} that share a size with another')
    for ps in candidates:
        heads = collections.defaultdict(list)
        for p in ps:                     # the first 64 KiB rules most out cheaply
            heads[_digest(p, 65536)].append(p)
        for same_head in heads.values():
            if len(same_head) < 2:
                continue
            full = collections.defaultdict(list)
            for p in same_head:
                full[_digest(p)].append(p)
            found += [(h, g) for h, g in full.items() if len(g) > 1]
        done += len(ps)
        progress(done, total, 'comparing files')
    groups, extra, extra_bytes = [], 0, 0
    for i, (h, g) in enumerate(sorted(found, key=lambda x: -os.path.getsize(x[1][0])), 1):
        rels = sorted((cfg.rel(p) for p in g), key=lambda r: _rank(cfg, r))
        size = os.path.getsize(g[0])
        groups.append({'id': f'd{i}', 'sha1': h[:12], 'size': size, 'files': rels, 'keep': rels[0]})
        extra += len(rels) - 1
        extra_bytes += size * (len(rels) - 1)
    return {'kind': 'duplicates', 'mode': 'file', 'groups': groups, 'moves': [], 'notes': [],
            'stats': {'scanned': n, 'groups': len(groups), 'extra': extra, 'extra_bytes': extra_bytes}}


def duplicate_moves(cfg, plan):
    """The moves a duplicates plan makes with its current keep choices, and the copies left alone
    because their Live Photo half is staying. Computed from the folder as it is now."""
    delete = plan.get('mode') == 'delete'   # remove the extra copies instead of filing them
    groups = [g for g in plan['groups'] if g['id'] not in set(plan.get('excluded', []))]
    marked = {rel: rel == g['keep'] for g in plan['groups'] for rel in g['files']}
    mate = {}
    for rel in marked:
        half = live_photos.partner(cfg.abs(rel))
        if half:
            mate[rel] = cfg.rel(half)
    taken, moves, protected = set(), [], []
    for g in groups:
        keep = g['keep']
        if keep not in g['files'] or not os.path.exists(cfg.abs(keep)):
            protected.append({'path': keep, 'why': 'the copy to keep is missing; group left alone'})
            continue
        kept_dir = os.path.dirname(_in_library(cfg, keep))
        if kept_dir.split('/')[0] == DUPS:
            kept_dir = kept_dir.split('/', 1)[1] if '/' in kept_dir else ''
        for rel in g['files']:
            if rel == keep or not os.path.exists(cfg.abs(rel)):
                continue
            if rel in mate and marked.get(mate[rel], True):   # kept, or not a duplicate at all
                protected.append({'path': rel, 'why': f'its Live Photo half {mate[rel]} is staying'})
                continue
            if delete:   # the copy to keep is named, and checked again at the moment of deletion
                moves.append({'id': len(moves), 'src': rel, 'dst': '', 'kind': 'delete',
                              'why': f'identical to {keep}', 'group': g['id'], 'keep': keep})
                continue
            target = os.path.join(cfg.root, DUPS, kept_dir)
            if os.path.dirname(cfg.abs(rel)) == target.rstrip('/'):
                continue   # already filed beside its kept copy
            dst = os.path.join(target, os.path.basename(rel))
            b, e = os.path.splitext(dst)
            n, c = 1, dst
            while c.lower() in taken or os.path.lexists(c):
                c = f'{b}_{n}{e}'
                n += 1
            taken.add(c.lower())
            moves.append({'id': len(moves), 'src': rel, 'dst': cfg.rel(c), 'kind': 'duplicate',
                          'why': f'copy of {keep}', 'group': g['id']})
    return moves, protected


# ----------------------------------------------------------------------------------------------
# Applying and undoing
# ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------
# Immich's trash
# ----------------------------------------------------------------------------------------------
def _immich_file(cfg, immich_path):
    """Where an Immich asset's file is in this library: (status, relative path or None)."""
    prefix = cfg.immich_prefix + '/'
    if not immich_path or not immich_path.startswith(prefix):
        return 'outside', None   # in Immich's own storage, not in this folder
    rel = immich_path[len(prefix):]
    try:
        path = cfg.abs(rel)
    except ValueError:
        return 'outside', None
    if os.path.islink(path):
        return 'symlink', rel
    return ('file' if os.path.isfile(path) else 'missing'), rel


def plan_immich(cfg, client, progress=_noop):
    """Every asset in Immich's trash, and where its file is in this library. A Live Photo's clip
    is shown with its still. Changes nothing here or in Immich."""
    assets = client.trashed(progress)
    by_id = {a['id']: a for a in assets}
    clip_ids = {a['livePhotoVideoId'] for a in assets if a.get('livePhotoVideoId') in by_id}
    items, seen = [], set()
    for a in assets:
        if a['id'] in clip_ids:
            continue
        status, rel = _immich_file(cfg, a.get('originalPath'))
        if rel in seen:
            continue
        seen.add(rel)
        item = {'id': a['id'], 'name': a.get('originalFileName') or os.path.basename(a.get('originalPath') or ''),
                'immich_path': a.get('originalPath'), 'type': a.get('type'), 'status': status, 'rel': rel,
                'size': 0, 'sha1': immich_api.checksum_hex(a.get('checksum')), 'clip': None}
        if status == 'file':
            item['size'] = os.path.getsize(cfg.abs(rel))
            clip = by_id.get(a.get('livePhotoVideoId'))
            if clip:
                cstatus, crel = _immich_file(cfg, clip.get('originalPath'))
                if cstatus == 'file':
                    item['clip'] = {'rel': crel, 'size': os.path.getsize(cfg.abs(crel)),
                                    'sha1': immich_api.checksum_hex(clip.get('checksum'))}
            if not item['clip'] and a.get('type') == 'IMAGE':
                half = live_photos.partner(cfg.abs(rel))   # its clip, found by name
                if half and os.path.isfile(half) and half.lower().endswith('.mov'):
                    item['clip'] = {'rel': cfg.rel(half), 'size': os.path.getsize(half), 'sha1': ''}
        items.append(item)
    kinds = collections.Counter(i['status'] for i in items)
    on_disk = [i for i in items if i['status'] == 'file']
    return {'kind': 'immich', 'mode': 'file', 'items': items, 'moves': [], 'notes': [],
            'stats': {'assets': len(items), 'kinds': dict(kinds), 'live': sum(1 for i in on_disk if i['clip']),
                      'bytes': sum(i['size'] + (i['clip'] or {}).get('size', 0) for i in on_disk)}}


def immich_moves(cfg, plan):
    """The removals a trash plan makes with its current ticks: each file that is on disk, with its
    Live Photo clip. By default a file is moved under _removed/ (undo puts it back); in delete mode
    it is removed for good, but only if it is still the file Immich trashed (same SHA-1)."""
    delete = plan.get('mode') == 'delete'
    taken, moves = set(), []
    for item in plan['items']:
        if item['status'] != 'file' or not os.path.isfile(cfg.abs(item['rel'])):
            continue
        for rel, sha1 in ((item['rel'], item['sha1']), *(((item['clip']['rel'], item['clip']['sha1']),) if item['clip'] else ())):
            m = {'id': len(moves), 'src': rel, 'dst': '', 'kind': 'purge' if delete else 'remove',
                 'why': 'in Immich\u2019s trash' + (' (its Live Photo clip)' if rel != item['rel'] else ''),
                 'group': f'immich:{item["id"]}', 'sha1': sha1}
            if not delete:
                n, c = 1, os.path.join(cfg.root, REMOVED, rel)
                b, e = os.path.splitext(c)
                while c.lower() in taken or os.path.lexists(c):
                    c = f'{b}_{n}{e}'
                    n += 1
                taken.add(c.lower())
                m['dst'] = cfg.rel(c)
            moves.append(m)
    return moves


def purge_file(cfg, m):
    """Delete one file Immich trashed, but only if it is still that file: a regular file (never a
    link) whose SHA-1 is the one Immich recorded. Recorded, and cannot be undone."""
    src = cfg.abs(m['src'])
    entry = {'src': m['src'], 'dst': '', 'kind': 'purge', 'status': 'deleted', 'note': ''}
    if os.path.islink(src) or not os.path.isfile(src):
        entry.update(status='skipped', note='the file is no longer there')
    elif m.get('sha1') and _digest(src) != m['sha1']:
        entry.update(status='skipped', note='it is not the file Immich trashed any more (different content)')
    else:
        entry['sha1'] = _digest(src)
        try:
            os.remove(src)
        except OSError as e:
            entry.update(status='error', note=str(e))
    return entry


def selected_moves(plan, cfg=None):
    """The moves of a plan that are ticked. A pair, an event or a duplicate group is ticked or
    unticked as a whole."""
    moves = (duplicate_moves(cfg, plan)[0] if plan['kind'] == 'duplicates'
             else immich_moves(cfg, plan) if plan['kind'] == 'immich' else plan['moves'])
    off_groups, off_kinds = set(plan.get('excluded', [])), set(plan.get('excluded_kinds', []))
    return [m for m in moves if (m.get('group') or f'm{m["id"]}') not in off_groups and m['kind'] not in off_kinds]


def _make_dirs(cfg, folder):
    new, d = [], folder
    while d.startswith(cfg.root + os.sep) and not os.path.isdir(d):
        new.append(d)
        d = os.path.dirname(d)
    os.makedirs(folder, exist_ok=True)
    st = os.stat(cfg.root)
    for d in new:
        try:
            os.chown(d, st.st_uid, st.st_gid)
        except PermissionError:
            pass


def apply_moves(cfg, moves, progress=_noop, record=None):
    """Make the moves, never overwriting anything. `record` is called with the run so far every
    few moves, so a crash still leaves a record to undo from. Returns the run."""
    run = {'started': time.time(), 'finished': None, 'moves': [], 'undone': None}
    total = len(moves)
    for i, m in enumerate(moves, 1):
        if m['kind'] in ('delete', 'purge'):
            run['moves'].append((delete_copy if m['kind'] == 'delete' else purge_file)(cfg, m))
            progress(i, total, 'deleting')
            continue
        src, dst = cfg.abs(m['src']), cfg.abs(m['dst'])
        entry = {'src': m['src'], 'dst': m['dst'], 'kind': m['kind'], 'status': 'moved', 'note': ''}
        if not os.path.lexists(src):
            entry.update(status='skipped', note='the file is no longer there')
        elif os.path.lexists(dst):
            entry.update(status='skipped', note='something is already at the destination')
        else:
            try:
                _make_dirs(cfg, os.path.dirname(dst))
                os.rename(src, dst)
            except OSError as e:
                entry.update(status='error', note=str(e))
        run['moves'].append(entry)
        progress(i, total, 'moving')
        if record and i % 200 == 0:
            record(run)
    empty = prune_empty(cfg, True)
    run['pruned'] = [cfg.rel(d) for d in empty]
    run['finished'] = time.time()
    if record:
        record(run)
    return run


def delete_copy(cfg, m):
    """Delete one extra copy, but only if it is still byte-for-byte the copy that is being kept.
    A missing or changed keeper means nothing is deleted. This is the one place a file is removed;
    a deletion is recorded with the sha1 it had, and cannot be undone."""
    src, keep = cfg.abs(m['src']), cfg.abs(m['keep'])
    entry = {'src': m['src'], 'dst': '', 'kind': 'delete', 'status': 'deleted', 'note': '', 'keep': m['keep']}
    if not os.path.isfile(src):
        entry.update(status='skipped', note='the file is no longer there')
    elif src == keep or not os.path.isfile(keep):
        entry.update(status='skipped', note='the copy being kept is missing')
    elif os.path.getsize(src) != os.path.getsize(keep) or _digest(src) != _digest(keep):
        entry.update(status='skipped', note='no longer identical to the copy being kept')
    else:
        entry['sha1'] = _digest(src)
        try:
            os.remove(src)
        except OSError as e:
            entry.update(status='error', note=str(e))
    return entry


def undo_run(cfg, run, progress=_noop):
    """Put back every move of the run that was made, newest first. Never overwrites."""
    done = [m for m in run['moves'] if m['status'] == 'moved']
    result = {'restored': 0, 'skipped': [], 'not_restorable': sum(1 for m in run['moves'] if m['status'] == 'deleted')}
    for i, m in enumerate(reversed(done), 1):
        src, dst = cfg.abs(m['src']), cfg.abs(m['dst'])
        if not os.path.lexists(dst):
            result['skipped'].append({'path': m['dst'], 'note': 'no longer there'})
        elif os.path.lexists(src):
            result['skipped'].append({'path': m['src'], 'note': 'the original place is taken'})
        else:
            _make_dirs(cfg, os.path.dirname(src))
            os.rename(dst, src)
            result['restored'] += 1
        progress(i, len(done), 'putting back')
    prune_empty(cfg, True)
    return result
