"""Zip files dropped in the inbox: unpacked beside themselves, checked, then deleted.

The Inbox scan starts here. Every .zip under _inbox is extracted into the folder it sits in (a
Google Takeout zip becomes a Takeout folder next to it), and only when every file in it is on disk
with the exact bytes the zip holds is the zip deleted. A zip that cannot be fully checked is kept
and the scan says why. Nothing is ever overwritten: a file that is already there with the same
bytes counts as unpacked, one with different bytes keeps its place and the new one gets " (1)".
"""
import os
import shutil
import time
import zipfile
import zlib

from . import core

SETTLE = 60                      # a zip changed in the last minute may still be copying in
CHUNK = 8 << 20
JUNK = ('__MACOSX/',)            # macOS resource forks and Finder litter, not photos
PART = '.unzipping'


def _crc(path):
    c = 0
    with open(path, 'rb') as fh:
        while True:
            b = fh.read(CHUNK)
            if not b:
                return c
            c = zlib.crc32(b, c)


def _same(path, info):
    return os.path.isfile(path) and os.path.getsize(path) == info.file_size and _crc(path) == info.CRC


def _spot(dest, info):
    """Where this member goes: its own path, or, if that holds something different, the first
    "name (n).ext" that is free or already holds exactly this member. (path, already_there)."""
    if not os.path.lexists(dest):
        return dest, False
    if _same(dest, info):
        return dest, True
    base, ext = os.path.splitext(dest)
    n = 1
    while True:
        cand = f'{base} ({n}){ext}'
        if not os.path.lexists(cand):
            return cand, False
        if _same(cand, info):
            return cand, True
        n += 1


def zips(cfg):
    base = os.path.join(cfg.root, '_inbox')
    return [p for p in core.files_under(base) if p.lower().endswith('.zip')] if os.path.isdir(base) else []


def _clean(cfg):
    """Half-written files from an unpack that was cut short."""
    base = os.path.join(cfg.root, '_inbox')
    for d, _, fs in os.walk(base):
        for f in fs:
            if f.endswith(PART):
                os.remove(os.path.join(d, f))


def unpack(cfg, path, progress, spent):
    """Unpack one zip beside itself and check it. Returns {'zip', 'files', 'deleted', 'note'}.
    `spent` is a list [bytes done] shared across zips for progress."""
    rel, folder = cfg.rel(path), os.path.dirname(path)
    out = {'zip': rel, 'files': 0, 'deleted': False, 'note': ''}
    st = os.stat(path)
    if time.time() - st.st_mtime < SETTLE:
        out['note'] = 'it was changed a moment ago, so it may still be copying in; it is unpacked on a later scan'
        return out
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as e:
        out['note'] = f'it is not a readable zip ({e})'
        return out
    with zf:
        members = [i for i in zf.infolist() if not i.is_dir() and not i.filename.startswith(JUNK) and os.path.basename(i.filename) != '.DS_Store']
        if not members:
            out['note'] = 'it holds no files'
            return out
        if any(i.flag_bits & 1 for i in members):
            out['note'] = 'it is password protected'
            return out
        if len({os.path.normpath(i.filename) for i in members}) != len(members):
            out['note'] = 'it holds two files with the same path, so it was not unpacked'
            return out
        plan = []
        for i in members:
            dest = os.path.normpath(os.path.join(folder, i.filename))
            if i.filename.startswith(('/', '\\')) or not dest.startswith(folder + os.sep):
                out['note'] = f'it holds a path that leaves its folder ({i.filename}), so it was not unpacked'
                return out
            plan.append((i, *_spot(dest, i)))
        need = sum(i.file_size for i, _, there in plan if not there)
        if shutil.disk_usage(folder).free < need + (1 << 30):
            out['note'] = f'there is not enough free space to unpack it ({need / 2**30:.1f} GiB needed)'
            return out
        written = []
        try:
            for n, (i, target, there) in enumerate(plan, 1):
                if not there:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    part = target + PART
                    try:
                        with zf.open(i) as src, open(part, 'wb') as dst:
                            while True:
                                b = src.read(CHUNK)
                                if not b:
                                    break
                                dst.write(b)
                                spent[0] += len(b)
                                progress(spent[0] // (1 << 20), None, f'unpacking {os.path.basename(path)} · file {n:,} of {len(plan):,}')
                        os.replace(part, target)
                    finally:
                        if os.path.exists(part):
                            os.remove(part)
                    written.append(target)
                    try:
                        os.utime(target, (time.time(), time.mktime((*i.date_time, 0, 0, -1))))   # keep the date the file had
                    except (OverflowError, ValueError, OSError):
                        pass
                else:
                    spent[0] += i.file_size
        except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError) as e:
            for t in written:
                os.remove(t)
            out['note'] = f'unpacking failed ({e}); what it had written was removed and the zip was kept'
            return out
    # Read everything back from the disk. Only a file that matches the zip byte for byte counts.
    bad = []
    for n, (i, target, _) in enumerate(plan, 1):
        if not _same(target, i):
            bad.append(target)
        progress(None, None, f'checking {os.path.basename(path)} · file {n:,} of {len(plan):,}')
    out['files'] = len(plan)
    if bad:
        for t in bad:
            if t in written and os.path.exists(t):
                os.remove(t)
        out['note'] = f'{len(bad):,} file{"s" if len(bad) != 1 else ""} did not match what the zip holds, so the zip was kept'
        return out
    now = os.stat(path)
    if (now.st_size, now.st_mtime_ns) != (st.st_size, st.st_mtime_ns):
        out['note'] = 'it changed while it was being unpacked, so it was kept'
        return out
    os.remove(path)
    out['deleted'] = True
    return out


def unpack_all(cfg, progress=core._noop):
    """Unpack, check and delete every zip in the inbox. Zips found inside those (up to three
    levels) are handled too. Returns one entry per zip."""
    _clean(cfg)
    report, seen = [], set()
    for _ in range(3):
        found = [p for p in zips(cfg) if p not in seen]
        if not found:
            break
        spent = [0]
        total = sum(os.path.getsize(p) for p in found) // (1 << 20)
        progress(0, total, f'unpacking {len(found)} zip file{"s" if len(found) != 1 else ""}')
        for p in found:
            seen.add(p)
            report.append(unpack(cfg, p, progress, spent))
    return report


def notes(report):
    """What to tell the person, one line each."""
    done = [r for r in report if r['deleted']]
    out = []
    if done:
        files = sum(r['files'] for r in done)
        out.append(f'Unpacked {len(done)} zip file{"s" if len(done) != 1 else ""} ({files:,} files), checked every file against the zip, then deleted the zip.')
    out += [f'Kept {os.path.basename(r["zip"])}: {r["note"]}.' for r in report if not r['deleted']]
    return out
