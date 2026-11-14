"""Photos with no recording date, set aside in _no_date, and giving them one.

A date is written into the file itself (the same tags the sorter reads), so it travels with the
photo into Immich and any other app. The file then goes to _inbox/loose, where the next inbox
scan files it by that date, checking for duplicates and Live Photo pairs like any other photo.
"""
import datetime
import os
import re
import subprocess

from . import core
from . import previews

# A date typed into a file name: 2023-06-14, 20230614, 2023_06_14. Not part of a longer number,
# so the 18-digit ids some exports use do not produce a made-up date.
NAME_DATE = re.compile(r'(?<!\d)((?:19|20)\d\d)[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])(?!\d)')


def hint(name):
    m = NAME_DATE.search(name)
    if not m:
        return ''
    try:
        datetime.date(*map(int, m.groups()))
    except ValueError:
        return ''
    return '-'.join(m.groups())


def files(cfg):
    """The media set aside for having no recording date."""
    base = os.path.join(cfg.root, core.NODATE)
    out = []
    for p in core.files_under(base) if os.path.isdir(base) else []:
        if core.is_media(p):
            st = os.stat(p)
            out.append({'path': cfg.rel(p), 'name': os.path.basename(p), 'size': st.st_size,
                        'modified': st.st_mtime, 'video': previews.is_video(p), 'hint': hint(os.path.basename(p))})
    return out


def stamp(date, time='12:00'):
    """'YYYY-MM-DD' and 'HH:MM' as ExifTool writes them, refusing anything that is not a real,
    plausible moment."""
    try:
        when = datetime.datetime.strptime(f'{date} {time or "12:00"}', '%Y-%m-%d %H:%M')
    except ValueError:
        raise ValueError('give the date as YYYY-MM-DD and the time as HH:MM') from None
    if not (1970 <= when.year <= datetime.date.today().year + 1):
        raise ValueError(f'{when.year} is not a plausible year for a photo')
    return when.strftime('%Y:%m:%d %H:%M:%S')


def write_date(path, when):
    """Write the date into the file. ExifTool replaces the file in one step, so a failure leaves
    the original untouched. Returns '' when the file now reads as dated, else why not."""
    tags = [f'-AllDates={when}']
    if previews.is_video(path):
        tags += [f'-MediaCreateDate={when}', f'-TrackCreateDate={when}']
    try:
        done = subprocess.run(['exiftool', '-overwrite_original', '-api', 'QuickTimeUTC', *tags, path],
                              capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        return 'ExifTool is not installed'
    except subprocess.TimeoutExpired:
        return 'ExifTool took too long'
    if done.returncode != 0:
        said = (done.stderr or done.stdout).strip()
        return said.splitlines()[-1][:200] if said else 'ExifTool failed'
    if path not in core.recording_months([path]):
        return 'this file type cannot hold a date'
    return ''


def set_dates(cfg, rels, when, progress=core._noop, record=None):
    """Date each file, then move the dated ones into _inbox/loose. Returns a run, like an apply:
    the moves can be undone, the dates written stay."""
    done, failed = [], []
    for i, rel in enumerate(rels, 1):
        path = cfg.abs(rel)
        why = write_date(path, when) if os.path.isfile(path) else 'the file is no longer there'
        (failed if why else done).append({'src': rel, 'note': why} if why else rel)
        progress(i, len(rels), 'writing dates')
    loose = os.path.join(cfg.root, *core.LOOSE)
    taken, moves = set(), []
    for rel in done:
        b, e = os.path.splitext(os.path.basename(rel))
        n, name = 0, b + e
        while name.lower() in taken or os.path.lexists(os.path.join(loose, name)):
            n += 1
            name = f'{b}_{n}{e}'
        taken.add(name.lower())
        moves.append({'src': rel, 'dst': cfg.rel(os.path.join(loose, name)), 'kind': 'dated',
                      'why': f'date set to {when[:10]}'})
    run = core.apply_moves(cfg, moves, progress, record)
    run['moves'] += [{'src': f['src'], 'dst': '', 'kind': 'dated', 'status': 'error', 'note': f['note']} for f in failed]
    run['dated'] = when
    if record:
        record(run)
    return run
