#!/usr/bin/env python3
"""A stand-in for exiftool, for tests and the local demo: dates come from a JSON map.

FAKE_DATES is a JSON file of {path relative to ROOT: "YYYY-MM"}. Anything not in it has no date.
Understands the calls photo-jobs makes:
  exiftool -json ... <paths>          read dates (and a width, height and camera for the viewer)
  exiftool -AllDates=<when> ... <p>   write a date: it lands in the map, and reads back
  exiftool -b -ThumbnailImage <p>     an embedded thumbnail: there never is one
"""
import json
import os
import sys

args = sys.argv[1:]
if '-b' in args:
    sys.exit(0)
dates_file = os.environ['FAKE_DATES']
dates = json.load(open(dates_file))
paths = [p for p in args if not p.startswith('-') and p not in ('QuickTimeUTC', '%Y-%m', '%Y-%m-%d %H:%M:%S')]
when = next((a.split('=', 1)[1] for a in args if a.startswith('-AllDates=')), None)
if when:
    if os.environ.get('FAKE_CANNOT_WRITE') and any(p.endswith(os.environ['FAKE_CANNOT_WRITE']) for p in paths):
        print('Warning: Error writing: format not supported', file=sys.stderr)
        sys.exit(0)
    for p in paths:
        dates[os.path.relpath(p, os.environ['ROOT'])] = when[:4] + '-' + when[5:7]
    json.dump(dates, open(dates_file, 'w'))
    print('    1 image files updated')
    sys.exit(0)
looks = '-ImageWidth' in args
out = []
for p in paths:
    rel = os.path.relpath(p, os.environ['ROOT'])
    out.append({'SourceFile': p, **({'DateTimeOriginal': dates[rel]} if rel in dates else {}),
                **({'ImageWidth': 160, 'ImageHeight': 120, 'Model': 'Demo camera'} if looks else {})})
print(json.dumps(out))
