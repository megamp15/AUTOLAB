#!/usr/bin/env python3
"""A stand-in for exiftool, for tests and the local demo.

FAKE_DATES is a JSON file of {path relative to ROOT: "YYYY-MM" or a full "YYYY:MM:DD HH:MM:SS"}.
FAKE_META is a JSON file of {path: {"lat", "lon", "alt", "desc"}} (created on first write).
Anything not in them has no date / location / description. It understands the calls photo-jobs makes:
  exiftool -json [-n] ... <paths>      read dates (and width, height, camera, location, description)
  exiftool -Tag=value ... <path>       write (a date, GPS, a description); an empty value removes the tag
  exiftool -b -ThumbnailImage <p>      an embedded thumbnail: there never is one
"""
import json
import os
import re
import sys

args = sys.argv[1:]
if '-b' in args:
    sys.exit(0)
root = os.environ['ROOT']
dates_file = os.environ['FAKE_DATES']
meta_file = os.environ.get('FAKE_META', dates_file + '.meta')
dates = json.load(open(dates_file))
meta = json.load(open(meta_file)) if os.path.exists(meta_file) else {}
paths = [p for p in args if not p.startswith('-') and p not in ('QuickTimeUTC', '%Y-%m', '%Y-%m-%d %H:%M:%S')]
writes = [a[1:].split('=', 1) for a in args if re.match(r'^-[\w:-]+=', a)]
if writes:
    if os.environ.get('FAKE_CANNOT_WRITE') and any(p.endswith(os.environ['FAKE_CANNOT_WRITE']) for p in paths):
        print('Warning: Error writing: format not supported', file=sys.stderr)
        sys.exit(0)
    for p in paths:
        rel = os.path.relpath(p, root)
        m = meta.setdefault(rel, {})
        sign = {'GPSLatitudeRef': -1 if any(t == 'GPSLatitudeRef' and v == 'S' for t, v in writes) else 1,
                'GPSLongitudeRef': -1 if any(t == 'GPSLongitudeRef' and v == 'W' for t, v in writes) else 1}
        for tag, val in writes:
            name = tag.split(':')[-1]
            if name in ('AllDates', 'DateTimeOriginal', 'CreateDate', 'ModifyDate', 'MediaCreateDate', 'TrackCreateDate'):
                if val:
                    dates[rel] = val
                elif name in ('DateTimeOriginal', 'AllDates'):
                    dates.pop(rel, None)
            elif name == 'GPSLatitude':
                if val == '':
                    m.pop('lat', None)
                else:
                    m['lat'] = float(val) * (sign['GPSLatitudeRef'] if not tag.startswith('XMP') else 1)
            elif name == 'GPSLongitude':
                if val == '':
                    m.pop('lon', None)
                else:
                    m['lon'] = float(val) * (sign['GPSLongitudeRef'] if not tag.startswith('XMP') else 1)
            elif name == 'GPSAltitude' and val == '':
                m.pop('alt', None)
            elif name in ('ImageDescription', 'Description'):
                if val:
                    m['desc'] = val
                else:
                    m.pop('desc', None)
    json.dump(dates, open(dates_file, 'w'))
    json.dump(meta, open(meta_file, 'w'))
    print('    1 image files updated')
    sys.exit(0)
raw = '-n' in args
looks = '-ImageWidth' in args
out = []
for p in paths:
    rel = os.path.relpath(p, root)
    row = {'SourceFile': p}
    if rel in dates:
        v = dates[rel]
        row['DateTimeOriginal'] = v if raw or len(v) == 7 else v[:4] + '-' + v[5:7]
        if raw:
            row['CreateDate'] = row['DateTimeOriginal']
    m = meta.get(rel, {})
    if 'lat' in m:
        row['GPSLatitude'], row['GPSLongitude'] = m['lat'], m['lon']
    if 'desc' in m:
        row['ImageDescription'] = m['desc']
    if looks or raw:
        row.update(ImageWidth=160, ImageHeight=120, Model='Demo camera')
    out.append(row)
print(json.dumps(out))
