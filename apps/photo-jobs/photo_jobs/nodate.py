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


# The time that follows a date in a name: 2018-06-03_17-15-00, 20230614_171500, 2023-06-14 17.15.00.
NAME_TIME = re.compile(r'[ _T-]((?:[01]\d|2[0-3]))[-_.:]?([0-5]\d)[-_.:]?([0-5]\d)(?!\d)')


def _named(name):
    m = NAME_DATE.search(name)
    if not m:
        return None
    try:
        datetime.date(*map(int, m.groups()))
    except ValueError:
        return None
    return m


def hint(name):
    m = _named(name)
    return '-'.join(m.groups()) if m else ''


def hint_time(name):
    """HH:MM:SS when the name has a time right after its date, else ''."""
    m = _named(name)
    t = NAME_TIME.match(name, m.end()) if m else None
    return ':'.join(t.groups()) if t else ''


def files(cfg):
    """The media set aside for having no recording date."""
    base = os.path.join(cfg.root, core.NODATE)
    out = []
    for p in core.files_under(base) if os.path.isdir(base) else []:
        if core.is_media(p):
            st = os.stat(p)
            out.append({'path': cfg.rel(p), 'name': os.path.basename(p), 'size': st.st_size,
                        'modified': st.st_mtime, 'video': previews.is_video(p), 'hint': hint(os.path.basename(p)),
                        'hint_time': hint_time(os.path.basename(p))})
    return out


def stamp(date, time='12:00'):
    """'YYYY-MM-DD' and 'HH:MM' as ExifTool writes them, refusing anything that is not a real,
    plausible moment."""
    when = None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            when = datetime.datetime.strptime(f'{date} {time or "12:00"}', fmt)
            break
        except ValueError:
            pass
    if when is None:
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


def real_name(path):
    """The path with the extension its contents call for, when the file is named as something it is
    not (a JPEG called .cr2). '' when it is not that, or the right name is already taken."""
    try:
        got = subprocess.run(['exiftool', '-s3', '-FileTypeExtension', path], capture_output=True, text=True, timeout=120).stdout.strip().lower()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ''
    new = os.path.splitext(path)[0] + '.' + got
    if not re.fullmatch(r'[a-z0-9]{2,5}', got) or new.lower() == path.lower() or os.path.lexists(new):
        return ''
    return new


def name_dates(rels, time=''):
    """({rel: moment} for the files whose own name holds a date, [{'src', 'note'}] for the rest).
    The time of day comes from the name when it has one, else from `time`."""
    whens, rejected = {}, []
    for rel in rels:
        name = os.path.basename(rel)
        if not hint(name):
            rejected.append({'src': rel, 'note': 'no date in the file name'})
            continue
        try:
            whens[rel] = stamp(hint(name), hint_time(name) or time)
        except ValueError as e:
            rejected.append({'src': rel, 'note': str(e)})
    return whens, rejected


def set_dates(cfg, rels, when, progress=core._noop, record=None, rejected=()):
    """Date each file, then move the dated ones into _inbox/loose. Returns a run, like an apply:
    the moves can be undone, the dates written stay. `when` is one moment for every file, or a
    {rel: moment} for each its own."""
    done, failed, renamed, stamps = [], list(rejected), {}, {}
    for i, rel in enumerate(rels, 1):
        path = cfg.abs(rel)
        mine = when[rel] if isinstance(when, dict) else when
        why = write_date(path, mine) if os.path.isfile(path) else 'the file is no longer there'
        if 'looks more like' in why:                 # a JPEG named .cr2: ExifTool will not write it until it has its real name
            fixed = real_name(path)
            if fixed and not os.rename(path, fixed):
                renamed[cfg.rel(fixed)] = os.path.basename(path)
                rel, path = cfg.rel(fixed), fixed
                why = write_date(path, mine)
        (failed if why else done).append({'src': rel, 'note': why} if why else rel)
        if not why:
            stamps[rel] = mine
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
                      'why': f'date set to {stamps[rel][:10]}'})
    run = core.apply_moves(cfg, moves, progress, record)
    for m in run['moves']:                           # say in the run which date each file got, and which were renamed
        if m['status'] == 'moved' and m['src'] in renamed:
            m['note'] = f'it was named {renamed[m["src"]]} but is really a {os.path.splitext(m["src"])[1][1:].upper()}, so it was renamed'
        if m['status'] == 'moved' and isinstance(when, dict):
            m['note'] = ('; '.join(x for x in (f'date set to {stamps[m["src"]].replace(":", "-", 2)}', m['note']) if x))
    run['moves'] += [{'src': f['src'], 'dst': '', 'kind': 'dated', 'status': 'error', 'note': f['note']} for f in failed]
    if isinstance(when, dict):
        run['dated_by_name'] = True
    else:
        run['dated'] = when
    if record:
        record(run)
    return run
