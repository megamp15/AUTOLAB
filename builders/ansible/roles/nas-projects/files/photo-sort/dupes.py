#!/usr/bin/env python3
"""Byte-for-byte duplicates across all of /media.

MODE=dupes        reads only: writes /job/duplicates.csv and /job/duplicates-summary.txt
MODE=dupes-apply  reads duplicates.csv (edit its keep column first if you like) and files every
                  copy marked "no" under _duplicates/ in the same folder as its kept copy
                  (_duplicates/2025/06/ beside 2025/06/), re-filing ones already there.
                  DUPLICATES=delete: deletes them instead, after checking each still matches
                  the kept copy. Never touches the kept copy. Every change is appended to
                  /job/moves.log next to the command that undoes it.
"""
import collections, csv, hashlib, os, re, shlex, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pairs as live_photos

ROOT = os.environ.get('ROOT', '/media')
JOB = os.environ.get('JOB', '/job')
MODE = os.environ.get('MODE', 'dupes')
DUPS = '_duplicates'
DELETE = os.environ.get('DUPLICATES', 'move') == 'delete'   # delete extra copies instead of moving them
SKIP = {'@eaDir', '#recycle', '#snapshot', '.DS_Store', 'Thumbs.db', '.stversions', '.stfolder'}
YEAR, MONTH = re.compile(r'^\d{4}$'), re.compile(r'^(0[1-9]|1[0-2])$')
CSV = os.path.join(JOB, 'duplicates.csv')
LIBNAME = os.environ.get('LIBRARY', 'library')


def in_library(rel):
    """library/2025/06/x -> 2025/06/x; anything else unchanged"""
    return rel.split('/', 1)[1] if rel.startswith(LIBNAME + '/') else rel
MEDIA = {'.jpg', '.jpeg', '.heic', '.heif', '.png', '.gif', '.webp', '.tif', '.tiff', '.dng',
         '.raw', '.cr2', '.cr3', '.nef', '.arw', '.orf', '.rw2', '.mov', '.mp4', '.m4v',
         '.avi', '.mkv', '.3gp', '.mts', '.m2ts'}


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def rank(rel):
    """Lower is a better copy to keep."""
    parts = in_library(rel).split('/')
    top = parts[0]
    if YEAR.match(top) and len(parts) >= 4 and MONTH.match(parts[1]):
        place = 0                       # inside an event folder in a month
    elif YEAR.match(top) and len(parts) == 3 and MONTH.match(parts[1]):
        place = 1                       # loose in a month folder
    elif top == '_no_date':
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
    # a clash suffix is _1, _2 added after a name that already ends in a number (IMG_8005_1);
    # IMG_8005 itself is not one
    suffixed = bool(re.search(r'\d_\d{1,2}\.[^.]+$', name)) or bool(re.search(r' copy|\(\d+\)', name, re.I))
    return (place, id_name, suffixed, len(rel), rel)


def digest(path, limit=None):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        if limit:
            h.update(f.read(limit))
        else:
            for b in iter(lambda: f.read(1 << 20), b''):
                h.update(b)
    return h.hexdigest()


def report():
    by_size = collections.defaultdict(list)
    n = 0
    for d, ds, fs in os.walk(ROOT):
        ds[:] = sorted(x for x in ds if x not in SKIP)
        for f in fs:
            # photos and videos only: sidecars (.xmp, .aae) of different photos are often
            # byte-identical, but each belongs to its own photo
            if f in SKIP or f.startswith('._') or os.path.splitext(f)[1].lower() not in MEDIA:
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
    log(f'{n} files; {sum(map(len, candidates))} share a size with another file, comparing those')
    groups, done = [], 0
    for ps in candidates:
        heads = collections.defaultdict(list)
        for p in ps:                     # first 64 KiB rules most out cheaply
            heads[digest(p, 65536)].append(p)
        for same_head in heads.values():
            if len(same_head) < 2:
                continue
            full = collections.defaultdict(list)
            for p in same_head:
                full[digest(p)].append(p)
            groups += [(h, g) for h, g in full.items() if len(g) > 1]
        done += len(ps)
        if done // 2000 != (done - len(ps)) // 2000:
            log(f'compared {done} / {sum(map(len, candidates))}')
    rows, extra_bytes, where = [], 0, collections.Counter()
    for i, (h, g) in enumerate(sorted(groups, key=lambda x: -os.path.getsize(x[1][0])), 1):
        rels = sorted((os.path.relpath(p, ROOT) for p in g), key=rank)
        size = os.path.getsize(g[0])
        for j, r in enumerate(rels):
            rows.append([i, h[:12], f'{size / 1048576:.1f}', 'yes' if j == 0 else 'no', r])
            if j:
                extra_bytes += size
                parts = in_library(r).split('/')
                where['/'.join(parts[:2]) if YEAR.match(parts[0]) and len(parts) > 2
                      else parts[0] if len(parts) > 1 else '(media root)'] += 1
    with open(CSV, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['group', 'sha1', 'size_mb', 'keep', 'path'])
        w.writerows(rows)
    extra = sum(1 for r in rows if r[3] == 'no')
    with open(os.path.join(JOB, 'duplicates-summary.txt'), 'w') as f:
        f.write(f'files scanned: {n}\nduplicate groups: {len(groups)}\nextra copies: {extra}\n'
                f'space the extra copies use: {extra_bytes / 1073741824:.1f} GiB\n\n'
                'where the extra copies are (folder: count):\n')
        f.writelines(f'  {k}: {v}\n' for k, v in where.most_common())
    log(open(os.path.join(JOB, 'duplicates-summary.txt')).read())
    log('DUPES REPORT DONE - nothing was moved; see duplicates.csv')


def apply():
    """Every copy marked no goes next to its kept copy's folder under _duplicates/ (2025/06/x ->
    _duplicates/2025/06/), copies already in _duplicates/ are re-filed the same way; with
    DUPLICATES=delete they are deleted instead, after checking they still match the kept copy."""
    groups = collections.defaultdict(list)
    with open(CSV, newline='') as f:
        for r in csv.DictReader(f):
            groups[r['group']].append(r)
    st, done, skipped = os.stat(ROOT), 0, 0
    # A Live Photo's still and clip are one photo. A half is only removed when its other half is
    # removed too: filing the still of copy B while copy A's clip is the one kept would leave a
    # clip with no still, or the reverse. Read once, before anything moves.
    marked = {r['path']: r['keep'].strip().lower() in ('yes', 'y', 'keep', '1') for rs in groups.values() for r in rs}
    other_half = {}
    for path in marked:
        mate = live_photos.partner(os.path.join(ROOT, path))
        if mate:
            other_half[path] = os.path.relpath(mate, ROOT)
    with open(os.path.join(JOB, 'moves.log'), 'a') as undo:
        for gid, rs in groups.items():
            keep = [r for r in rs if r['keep'].strip().lower() in ('yes', 'y', 'keep', '1')
                    and os.path.exists(os.path.join(ROOT, r['path']))]
            if not keep:
                log(f'group {gid}: no kept copy exists, left alone')
                skipped += len(rs)
                continue
            kept_rel = keep[0]['path']
            kept = os.path.join(ROOT, kept_rel)
            kept_dir = os.path.dirname(in_library(kept_rel))
            if kept_dir.split('/')[0] == DUPS:
                kept_dir = kept_dir.split('/', 1)[1] if '/' in kept_dir else ''
            for r in rs:
                if r in keep:
                    continue
                src = os.path.join(ROOT, r['path'])
                if not os.path.exists(src):
                    continue
                mate = other_half.get(r['path'])
                if mate and marked.get(mate, True):   # kept, or not a duplicate at all
                    log(f'group {gid}: {r["path"]} left alone, its Live Photo half {mate} is staying')
                    skipped += 1
                    continue
                if DELETE:   # identical to the kept copy, checked again right now
                    if digest(kept) != digest(src):
                        log(f'group {gid}: {r["path"]} no longer matches the kept copy, left alone')
                        skipped += 1
                        continue
                    os.remove(src)
                    undo.write(f'# {time.strftime("%Y-%m-%d %H:%M:%S")} deleted duplicate (group {gid}, kept {kept_rel})\n'
                               f'mkdir -p {shlex.quote(os.path.dirname(src))} && cp -pn {shlex.quote(kept)} {shlex.quote(src)}\n')
                    done += 1
                    continue
                target_dir = os.path.join(ROOT, DUPS, kept_dir)
                if os.path.dirname(src) == target_dir.rstrip('/'):
                    continue   # already filed beside its kept copy
                dst = os.path.join(target_dir, os.path.basename(src))
                b, e = os.path.splitext(dst)
                n = 1
                while os.path.lexists(dst):
                    dst = f'{b}_{n}{e}'
                    n += 1
                new, d = [], os.path.dirname(dst)
                while d.startswith(ROOT + '/') and not os.path.isdir(d):
                    new.append(d)
                    d = os.path.dirname(d)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                for d in new:
                    os.chown(d, st.st_uid, st.st_gid)
                os.rename(src, dst)
                undo.write(f'# {time.strftime("%Y-%m-%d %H:%M:%S")} duplicate (group {gid}, kept {kept_rel})\n'
                           f'mkdir -p {shlex.quote(os.path.dirname(src))} && mv -n {shlex.quote(dst)} {shlex.quote(src)}\n')
                done += 1
    if not DELETE:   # folders the re-filing emptied
        base = os.path.join(ROOT, DUPS)
        for d, _, _ in os.walk(base, topdown=False):
            if d != base and not os.listdir(d):
                os.rmdir(d)
    log(f'DUPES APPLY DONE - {"deleted" if DELETE else "filed"} {done} extra copies'
        f'{"" if DELETE else " under " + DUPS + "/ beside their kept copy"}; {skipped} left alone')


if MODE == 'dupes':
    report()
elif MODE == 'dupes-apply':
    apply()
else:
    sys.exit(f'unknown MODE {MODE}')
