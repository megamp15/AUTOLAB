#!/usr/bin/env python3
"""Sort /media into library/YYYY/MM by recording time. Run by hand: MODE=plan first, then MODE=apply.

Where things are put decides what happens to them; names do not matter:
  _inbox/loose/    every photo and video is sorted on its own into library/YYYY/MM/
  _inbox/events/   each folder is one event and moves whole into library/YYYY/MM/<folder>: the month
                   most of its photos are from, or the month before that if it has at least
                   half as many (the event started there); names never decide
  library/YYYY/<folder>  a folder directly in a year folder (not a month) is an event too
An event that already exists in its month is merged into, never overwritten. Exact copies of
photos already sorted go to _duplicates/, photos without a recording time to _no_date/.
Every move is appended to /job/moves.log next to the command that undoes it.

MODE=plan   reads only; writes /job/plan.txt
MODE=apply  moves
"""
import collections, hashlib, json, os, re, shlex, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pairs as live_photos

ROOT = os.environ.get('ROOT', '/media')
JOB = os.environ.get('JOB', '/job')
# the sorted photos: <media>/library/YYYY/MM/... (the only folder Immich scans);
# _inbox, _duplicates and _no_date stay beside it in <media>
LIB = os.path.join(ROOT, os.environ.get('LIBRARY', 'library'))
MODE = os.environ.get('MODE', 'plan')
LOOSE, EVENTS = ('_inbox', 'loose'), ('_inbox', 'events')
NODATE, DUPS = '_no_date', '_duplicates'
# move (default): copies of photos already sorted go to _duplicates/. delete: they are deleted,
# after checking once more that the kept copy exists and is still byte-for-byte identical.
DELETE_DUPS = os.environ.get('DUPLICATES', 'move') == 'delete'
MEDIA = {'.jpg', '.jpeg', '.heic', '.heif', '.png', '.gif', '.webp', '.tif', '.tiff', '.dng',
         '.raw', '.cr2', '.cr3', '.nef', '.arw', '.orf', '.rw2', '.mov', '.mp4', '.m4v',
         '.avi', '.mkv', '.3gp', '.mts', '.m2ts'}
DATE_TAGS = ['DateTimeOriginal', 'SubSecDateTimeOriginal', 'CreationDate', 'CreateDate',
             'MediaCreateDate', 'TrackCreateDate', 'ContentCreateDate']
YEAR = re.compile(r'^\d{4}$')
MONTH = re.compile(r'^(0[1-9]|1[0-2])$')
NAMED = re.compile(r'^((?:19|20)\d\d)[_-](0[1-9]|1[0-2])[_-]')
SKIP = {'@eaDir', '#recycle', '#snapshot', '.DS_Store', 'Thumbs.db'}


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def files_under(base):
    for d, ds, fs in os.walk(base):
        ds[:] = sorted(x for x in ds if x not in SKIP)
        for f in sorted(fs):
            if f not in SKIP and not f.startswith('._'):
                yield os.path.join(d, f)


def is_media(p):
    return os.path.splitext(p)[1].lower() in MEDIA


def recording_months(paths):
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
        if len(paths) > 500:
            log(f'read dates: {min(i + 500, len(paths))} / {len(paths)}')
    return out


JUNK = {'.DS_Store', 'Thumbs.db', 'desktop.ini'}


def prune_empty(remove):
    """Folders left with nothing in them (or only .DS_Store / ._* / Thumbs.db) after files were
    moved or deleted by hand. remove=False only counts them. Never media itself or the inbox."""
    keep = {ROOT, LIB, os.path.join(ROOT, '_inbox'), os.path.join(ROOT, *LOOSE), os.path.join(ROOT, *EVENTS)}
    gone = []
    for d, ds, fs in os.walk(ROOT, topdown=False):
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


class Sorter:
    def __init__(self, apply):
        self.apply, self.moves, self.taken, self.hashes = apply, [], set(), {}
        self.sizes = collections.defaultdict(list)   # every sorted file, by size, for duplicates
        years = [os.path.join(LIB, y) for y in (os.listdir(LIB) if os.path.isdir(LIB) else []) if YEAR.match(y)]
        for base in years + [os.path.join(ROOT, NODATE)]:
            if os.path.isdir(base):
                for p in files_under(base):
                    self.sizes[os.path.getsize(p)].append(p)

    def sha1(self, p):
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

    def move(self, src, dst, why):
        self.moves.append((os.path.relpath(src, ROOT), os.path.relpath(dst, ROOT), why))
        if not self.apply:
            return
        new, d = [], os.path.dirname(dst)
        while d.startswith(ROOT + '/') and not os.path.isdir(d):
            new.append(d)
            d = os.path.dirname(d)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        st = os.stat(ROOT)
        for d in new:
            os.chown(d, st.st_uid, st.st_gid)
        if os.path.lexists(dst):
            raise FileExistsError(dst)
        os.rename(src, dst)
        with open(os.path.join(JOB, 'moves.log'), 'a') as f:
            f.write(f'# {time.strftime("%Y-%m-%d %H:%M:%S")} {why}\n'
                    f'mkdir -p {shlex.quote(os.path.dirname(src))} && mv -n {shlex.quote(dst)} {shlex.quote(src)}\n')

    def drop_duplicate(self, p, dup):
        """A copy of dup, which is already sorted: move it to _duplicates/, or delete it."""
        why = f'duplicate of {os.path.relpath(dup, ROOT)}'
        if not DELETE_DUPS:   # next to where the kept copy is: _duplicates/2025/06/... beside 2025/06/
            home = LIB if dup.startswith(LIB + '/') else ROOT   # _duplicates/2025/06/ mirrors library/2025/06/
            dest = self.free(os.path.join(ROOT, DUPS, os.path.relpath(os.path.dirname(dup), home), os.path.basename(p)))
            self.move(p, dest, why)
            return dest
        self.moves.append((os.path.relpath(p, ROOT), '(deleted)', 'deleted ' + why))
        if self.apply:
            fresh = lambda x: hashlib.sha1(open(x, 'rb').read()).hexdigest()
            if not os.path.isfile(dup) or fresh(dup) != fresh(p):
                raise RuntimeError(f'not deleted, kept copy missing or changed: {dup}')
            os.remove(p)
            with open(os.path.join(JOB, 'moves.log'), 'a') as f:
                f.write(f'# {time.strftime("%Y-%m-%d %H:%M:%S")} deleted {why}\n'
                        f'mkdir -p {shlex.quote(os.path.dirname(p))} && cp -pn {shlex.quote(dup)} {shlex.quote(p)}\n')
        return None

    def remember(self, p):
        self.sizes[os.path.getsize(p)].append(p)

    def sort_loose(self, files):
        media = [p for p in files if is_media(p)]
        side = {p for p in files if p.lower().endswith('.xmp')}
        months = recording_months(media)
        clip_of = live_photos.pairs(media)                 # clip -> still
        clips = {still: clip for clip, still in clip_of.items()}
        for p in media:
            if p in clip_of:
                continue   # sorted together with its still
            members = [p] + ([clips[p]] if p in clips else [])
            dups = [self.duplicate_of(m) for m in members]
            if all(dups):   # every half is already sorted: each is filed beside its copy
                dests = [self.drop_duplicate(m, d) for m, d in zip(members, dups)]
            else:   # new, or a pair with a half that is new: the pair is never split
                month = months.get(p) or next((months[m] for m in members if m in months), None)
                if len(members) == 1:
                    if month:
                        y, mo = month.split('-')
                        dests, why = [self.free(os.path.join(LIB, y, mo, os.path.basename(p)))], f'recorded {month}'
                    else:
                        dests, why = [self.free(os.path.join(ROOT, NODATE, os.path.relpath(p, ROOT)))], 'no recording time'
                else:
                    stem = os.path.splitext(os.path.basename(p))[0]
                    exts = [os.path.splitext(m)[1] for m in members]
                    if month:
                        y, mo = month.split('-')
                        folder, why = os.path.join(LIB, y, mo), f'recorded {month}'
                    else:
                        folder, why = os.path.join(ROOT, NODATE, os.path.relpath(os.path.dirname(p), ROOT)), 'no recording time'
                    dests = self.free_set(folder, stem, exts)
                    why += f'; Live Photo with {os.path.basename(members[1])}'
                for m, dest in zip(members, dests):
                    self.move(m, dest, why)
            for m, dup, dest in zip(members, dups, dests):
                if dest is None:
                    continue   # deleted; any sidecar of it stays where it is
                if not all(dups):   # later files in this run count it as sorted, at the path it now has
                    now = dest if self.apply else m
                    if now != m and m in self.hashes:
                        self.hashes[now] = self.hashes.pop(m)
                    self.remember(now)
                for sc in (m + '.xmp', os.path.splitext(m)[0] + '.xmp'):
                    if sc in side:
                        side.discard(sc)
                        self.move(sc, self.free(dest + '.xmp'), 'sidecar')
        return [p for p in files if not is_media(p) and (not p.lower().endswith('.xmp') or p in side)]

    def place_event(self, folder):
        files = list(files_under(folder))
        media = [p for p in files if is_media(p)]
        months = recording_months(media)
        if not months:
            log(f'event has no dated photos, left where it is: {os.path.relpath(folder, ROOT)}')
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
        dest = os.path.join(LIB, y, m, os.path.basename(folder))
        if os.path.abspath(folder) == os.path.abspath(dest):
            return []
        if not os.path.lexists(dest) and dest.lower() not in self.taken:
            self.taken.add(dest.lower())
            self.move(folder, dest, f'event {y}-{m} by {by} ({len(media)} photos; {mix})')
            return []
        left = []   # same event already in its month: merge file by file
        clip_of = live_photos.pairs(media)
        clips = {still: clip for clip, still in clip_of.items()}
        for p in files:
            if p in clip_of:
                continue   # merged together with its still
            members = [p] + ([clips[p]] if p in clips else [])
            dups = [self.duplicate_of(m, ignore=folder + '/') if is_media(m) else None for m in members]
            if all(dups):
                for m, d in zip(members, dups):
                    self.drop_duplicate(m, d)
                continue
            why = f'merged into {os.path.relpath(dest, ROOT)}'
            target = os.path.join(dest, os.path.relpath(p, folder))
            if len(members) == 1:
                self.move(p, self.free(target), why)
            else:
                stem = os.path.splitext(os.path.basename(target))[0]
                names = self.free_set(os.path.dirname(target), stem, [os.path.splitext(m)[1] for m in members])
                for m, name in zip(members, names):
                    self.move(m, name, why + '; Live Photo')
        return left

    def run(self):
        stray = sorted(y for y in os.listdir(ROOT) if YEAR.match(y) and os.path.isdir(os.path.join(ROOT, y)))
        if stray:
            log(f'NOTE: year folders outside {os.path.relpath(LIB, ROOT)}/: {", ".join(stray)} - move them into it')
        loose_dir, events_dir = os.path.join(ROOT, *LOOSE), os.path.join(ROOT, *EVENTS)
        for d in (loose_dir, events_dir):
            if self.apply:
                os.makedirs(d, exist_ok=True)
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
        for y in sorted(os.listdir(LIB) if os.path.isdir(LIB) else []):
            yp = os.path.join(LIB, y)
            if YEAR.match(y) and os.path.isdir(yp):
                for name in sorted(os.listdir(yp)):
                    p = os.path.join(yp, name)
                    if os.path.isdir(p) and not MONTH.match(name) and name not in SKIP:
                        left += self.place_event(p)
        if self.apply:   # folders this run emptied, inside the inbox
            for base in (loose_dir, events_dir):
                for d, _, _ in os.walk(base, topdown=False):
                    if d not in (loose_dir, events_dir) and not os.listdir(d):
                        os.rmdir(d)
        return left


if MODE not in ('plan', 'apply', 'dupes', 'dupes-apply', 'undo'):
    sys.exit(f'unknown MODE {MODE}')
print('\n' + '=' * 64, flush=True)
log(f'NEW RUN  MODE={MODE}  DUPLICATES={"delete" if DELETE_DUPS else "move"}  '
    + ('(changes files)' if MODE.endswith('apply') or MODE == 'undo' else '(reads only, changes nothing)'))
print('=' * 64, flush=True)
if MODE == 'undo':   # runs /job/undo.sh once (lines copied from moves.log), then renames it
    script = os.path.join(JOB, 'undo.sh')
    if not os.path.isfile(script):
        sys.exit('no undo.sh in the job folder, nothing to undo')
    lines = [l for l in open(script) if l.strip() and not l.startswith('#')]
    ok = sum(subprocess.run(['sh', '-c', l]).returncode == 0 for l in lines)
    os.rename(script, os.path.join(JOB, f'undo.done-{time.strftime("%Y%m%d-%H%M%S")}.sh'))
    log(f'UNDO DONE - {ok} of {len(lines)} lines ran; the script was renamed so it cannot run twice')
    empty = prune_empty(True)
    if empty:
        log(f'removed {len(empty)} empty folders')
    sys.exit(0)
if MODE.startswith('dupes'):   # the duplicate report and its cleanup live in dupes.py
    import runpy
    runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dupes.py'), run_name='__main__')
    empty = prune_empty(MODE == 'dupes-apply')
    if empty:
        log(f'{"removed" if MODE == "dupes-apply" else "next dupes-apply removes"} {len(empty)} empty folders: '
            + ', '.join(os.path.relpath(d, ROOT) for d in empty[:8]) + (' ...' if len(empty) > 8 else ''))
    sys.exit(0)
s = Sorter(MODE == 'apply')
left = s.run()
kinds = collections.Counter(w.split(' ')[0] for _, _, w in s.moves)
log(f'{"changed" if s.apply else "would change"} {len(s.moves)}: {dict(kinds)}; {len(left)} other files left where they are')
empty = prune_empty(s.apply)
if empty:
    log(f'{"removed" if s.apply else "next apply removes"} {len(empty)} empty folders: '
        + ', '.join(os.path.relpath(d, ROOT) for d in empty[:8]) + (' ...' if len(empty) > 8 else ''))
if not s.apply:
    with open(os.path.join(JOB, 'plan.txt'), 'w') as f:
        f.writelines(f'{a}\t{b}\t{w}\n' for a, b, w in s.moves)
        f.writelines(f'LEFT\t{os.path.relpath(x, ROOT)}\n' for x in left)
    log('PLAN DONE - nothing was moved; see plan.txt')
else:
    log('APPLY DONE - every move is in moves.log with its undo command')
