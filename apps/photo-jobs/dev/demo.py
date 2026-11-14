#!/usr/bin/env python3
"""Run Photo Jobs on a made-up library, to see and click through it locally.

    python3 apps/photo-jobs/dev/demo.py [folder] [port]

Builds a library under `folder` (default: a temp dir) with Live Photos, events, duplicates, an
event whose name disagrees with its photos and a few photos with no date, then serves the page.
Dates come from the stand-in exiftool and the Immich trash from a stand-in Immich, so no real photos,
ExifTool or Immich are needed. Run it again on
the same folder to start from where you left off; delete the folder to start over.
"""
import json
import os
import random
import stat
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

root = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix='photo-demo-'))
port = sys.argv[2] if len(sys.argv) > 2 else '8099'
media, state, tools = root / 'media', root / 'state', root / 'bin'
for d in (media, state, tools):
    d.mkdir(parents=True, exist_ok=True)

dates_file = root / 'dates.json'
if not dates_file.exists():
    rng, dates = random.Random(7), {}

    def put(rel, data, month=None):
        p = media / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
        if month:
            dates[rel] = month

    def blob(tag, n=2048):   # distinct, sized bytes, so size and hash comparisons are real
        return (tag.encode() + rng.randbytes(n))[:n]

    # already in the library
    for m, name in (('2025-05', 'IMG_2001'), ('2025-06', 'IMG_2044'), ('2025-06', 'IMG_2045')):
        y, mo = m.split('-')
        put(f'library/{y}/{mo}/{name}.HEIC', blob(name), m)
    put('library/2025/06/Lake_weekend/IMG_2100.JPG', b'lake-photo' * 300, '2025-06')
    put('library/2025/06/IMG_2100.JPG', b'lake-photo' * 300, '2025-06')   # the same photo, loose
    # loose uploads
    n = 3100
    for m in ('2025-06', '2025-06', '2025-07', '2025-07', '2025-07', '2025-08', '2025-09', '2025-09'):
        put(f'_inbox/loose/IMG_{n}.JPG', blob(f'loose{n}'), m)
        n += 1
    for i in range(6):   # Live Photos: the clip's own clock is a day-boundary off in two of them
        stem = f'IMG_{4000 + i}'
        month = '2025-07' if i < 4 else '2025-08'
        put(f'_inbox/loose/{stem}.HEIC', blob(stem), month)
        put(f'_inbox/loose/{stem}.MOV', blob(stem + 'v', 6000), month if i % 3 else '2025-09')
    put('_inbox/loose/IMG_2044.HEIC', (media / 'library/2025/06/IMG_2044.HEIC').read_bytes(), '2025-06')   # already have it
    put('_inbox/loose/scan_0001.jpg', blob('scan1'))
    put('_inbox/loose/scan_0002.jpg', blob('scan2'))
    put('_inbox/loose/IMG_3500.JPG', b'lake-photo' * 300, '2025-06')                                          # and this one
    put('_inbox/loose/notes.txt', 'not a photo')
    # events
    for i in range(14):
        put(f'_inbox/events/Beach_trip/IMG_{5000 + i}.JPG', blob(f'beach{i}'), '2025-07')
    for i in range(3):
        put(f'_inbox/events/Beach_trip/IMG_{5100 + i}.MOV', blob(f'beachv{i}', 5000), '2025-07')
    for i in range(5):
        put(f'_inbox/events/Road_trip/DSC_{i}.JPG', blob(f'road{i}'), '2025-05')
    for i in range(7):
        put(f'_inbox/events/Road_trip/DSC_{10 + i}.JPG', blob(f'roadb{i}'), '2025-06')
    for i in range(4):
        put(f'_inbox/events/2025-03 Birthday/IMG_{6000 + i}.JPG', blob(f'bday{i}'), '2025-04')
    put('_inbox/events/Receipts/r1.jpg', blob('r1'))   # an event with nothing to date it by
    dates_file.write_text(json.dumps(dates))
    # photos "deleted in Immich": files still in the library, one Live Photo, one already gone
    trashed = []
    for i, (rel, data) in enumerate([('library/2025/03/IMG_1001.JPG', b'march-a'), ('library/2025/03/IMG_1002.JPG', b'march-b'),
                                     ('library/2025/04/IMG_1100.HEIC', b'live-still'), ('library/2025/04/IMG_1100.MOV', b'live-clip'),
                                     ('library/2025/02/screenshot.png', b'shot')]):
        (media / rel).parent.mkdir(parents=True, exist_ok=True)
        (media / rel).write_bytes(data)
    (root / 'trashed.json').write_text(json.dumps([
        ('1', 'library/2025/03/IMG_1001.JPG', 'march-a', {}), ('2', 'library/2025/03/IMG_1002.JPG', 'march-b', {}),
        ('3', 'library/2025/04/IMG_1100.HEIC', 'live-still', {'livePhotoVideoId': '4'}),
        ('4', 'library/2025/04/IMG_1100.MOV', 'live-clip', {'type': 'VIDEO'}),
        ('5', 'library/2025/02/screenshot.png', 'shot', {}), ('6', 'library/2024/12/already_gone.jpg', 'x', {}),
        ('7', None, 'x', {'originalPath': '/data/upload/ab/cd/uploaded-in-immich.jpg', 'originalFileName': 'uploaded-in-immich.jpg'})]))

sys.path.insert(0, str(HERE))
from fake_immich import FakeImmich, sha1b64  # noqa: E402
assets = []
for id_, rel, content, extra in json.loads((root / 'trashed.json').read_text()):
    path = '/mnt/mahir-personal/' + rel if rel else extra['originalPath']
    assets.append({'id': id_, 'originalPath': path, 'originalFileName': os.path.basename(path), 'isTrashed': True,
                   'type': 'IMAGE', 'checksum': sha1b64(content), **extra})
immich = FakeImmich(assets, key='demo-key')

shim = tools / 'exiftool'
shim.write_text((HERE / 'fake_exiftool.py').read_text())
shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
os.environ.update(PATH=f'{tools}:{os.environ["PATH"]}', FAKE_DATES=str(dates_file), ROOT=str(media),
                  MEDIA_ROOT=str(media), STATE_DIR=str(state), PORT=port, BIND='127.0.0.1', IMMICH_URL=immich.url, IMMICH_API_KEY='demo-key')
print(f'demo library in {root}')
print(f'http://127.0.0.1:{port}/')
from photo_jobs import server  # noqa: E402
server.main()
