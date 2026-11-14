"""Seeing a photo before anything happens to it: cached thumbnails, a file's facts, byte comparison.

Thumbnails are made once and kept under <state>/thumbs. libvips makes them when it is installed
(it reads HEIC, which no browser but Safari shows); without it a photo the browser can show is
served as it is, and anything else falls back to the small preview the camera embedded.
"""
import hashlib
import json
import os
import subprocess
import tempfile
import threading

from . import core

NATIVE = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
VIDEO = {'.mov', '.mp4', '.m4v', '.avi', '.mkv', '.3gp', '.mts', '.m2ts'}
WIDTHS = (240, 640, 1600)          # the only sizes made, so the cache stays small
_slots = threading.BoundedSemaphore(3)   # a thumbnail is CPU work; the NAS has other jobs


class NoPreview(Exception):
    pass


def ext(path):
    return os.path.splitext(path)[1].lower()


def is_video(path):
    return ext(path) in VIDEO


def _width(w):
    return next((x for x in WIDTHS if x >= w), WIDTHS[-1])


def _vips(src, out, width):
    """Make the thumbnail with vipsthumbnail. The source goes through a plain symlink name,
    because libvips reads [brackets] in a file name as loader options."""
    with tempfile.TemporaryDirectory() as tmp:
        link = os.path.join(tmp, 'in' + ext(src))
        os.symlink(src, link)
        target = f'{out}.part.jpg[Q=82,strip]'
        for flags in (['--rotate'], []):       # older and newer libvips disagree about this flag
            done = subprocess.run(['vipsthumbnail', link, '-s', f'{width}x{width}', *flags, '-o', target],
                                  capture_output=True, timeout=120)
            if done.returncode == 0 and os.path.exists(out + '.part.jpg'):
                os.replace(out + '.part.jpg', out)
                return True
    return False


def _embedded(src, out):
    """The small JPEG the camera stored inside the file, when there is one."""
    for tag in ('ThumbnailImage', 'PreviewImage'):
        try:
            data = subprocess.run(['exiftool', '-b', f'-{tag}', src], capture_output=True, timeout=60).stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        if data[:2] == b'\xff\xd8':
            with open(out + '.part', 'wb') as f:
                f.write(data)
            os.replace(out + '.part', out)
            return True
    return False


def cover(cfg, rel):
    """The first photo in a folder (not a video), to stand for the folder: an event, an album. None if there is none."""
    seen = 0
    for path in core.files_under(cfg.abs(rel)):
        seen += 1
        if core.is_media(path) and not is_video(path):
            return cfg.rel(path)
        if seen > 400:
            break
    return None


def thumbnail(cfg, rel, width=240):
    """Path of a JPEG of this photo, at most `width` px on its long side (rounded up to a size
    that is made). Raises NoPreview for videos and files nothing can draw, FileNotFoundError for
    a path that is not there."""
    src = cfg.abs(rel)
    if os.path.isdir(src):              # a folder is shown by its first photo
        inside = cover(cfg, rel)
        if not inside:
            raise NoPreview(rel)
        return thumbnail(cfg, inside, width)
    if not core.is_media(src) or is_video(src):
        raise NoPreview(rel)
    st = os.stat(src)
    width = _width(width)
    key = hashlib.sha1(f'{rel}|{st.st_size}|{st.st_mtime_ns}|{width}'.encode()).hexdigest()
    out = os.path.join(cfg.state, 'thumbs', key[:2], key + '.jpg')
    if os.path.exists(out):
        return out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with _slots:
        if os.path.exists(out):
            return out
        try:
            if _vips(src, out, width):
                return out
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        if ext(src) in NATIVE:
            return src
        if _embedded(src, out):
            return out
    raise NoPreview(rel)


def facts(cfg, rel):
    """What the page shows beside a photo: size, when it was changed, and what ExifTool knows."""
    path = cfg.abs(rel)
    st = os.stat(path)
    out = {'path': rel, 'name': os.path.basename(path), 'size': st.st_size, 'modified': st.st_mtime,
           'video': is_video(path), 'width': None, 'height': None, 'taken': '', 'camera': '', 'duration': ''}
    try:
        res = subprocess.run(['exiftool', '-json', '-d', '%Y-%m-%d %H:%M:%S', '-api', 'QuickTimeUTC',
                              '-ImageWidth', '-ImageHeight', '-DateTimeOriginal', '-CreateDate', '-MediaCreateDate',
                              '-Make', '-Model', '-Duration', path], capture_output=True, text=True, timeout=60).stdout
        info = (json.loads(res or '[]') or [{}])[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        info = {}
    out['width'], out['height'] = info.get('ImageWidth'), info.get('ImageHeight')
    out['taken'] = str(next((info[t] for t in ('DateTimeOriginal', 'CreateDate', 'MediaCreateDate') if info.get(t)), ''))
    out['camera'] = ' '.join(str(info[t]) for t in ('Make', 'Model') if info.get(t))
    out['duration'] = str(info.get('Duration', ''))
    return out


def same_bytes(cfg, a, b):
    """True when the two files are byte for byte the same (size first, then SHA-1)."""
    pa, pb = cfg.abs(a), cfg.abs(b)
    if os.path.getsize(pa) != os.path.getsize(pb):
        return False
    return core._digest(pa) == core._digest(pb)
