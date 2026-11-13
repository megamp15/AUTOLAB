#!/usr/bin/env python3
"""A stand-in for exiftool, for tests and the local demo: dates come from a JSON map.

FAKE_DATES is a JSON file of {path relative to ROOT: "YYYY-MM"}. Anything not in it has no date.
Understands only the one call photo-jobs makes: exiftool -json ... <paths>.
"""
import json
import os
import sys

dates = json.load(open(os.environ['FAKE_DATES']))
out = []
for p in sys.argv[1:]:
    if p.startswith('-') or p in ('QuickTimeUTC', '%Y-%m'):
        continue
    rel = os.path.relpath(p, os.environ['ROOT'])
    out.append({'SourceFile': p, **({'DateTimeOriginal': dates[rel]} if rel in dates else {})})
print(json.dumps(out))
