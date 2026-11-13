"""Live Photos: a still and the short clip Apple saves beside it (IMG_1234.HEIC + IMG_1234.MOV).

The two files are one photo. They must be dated together, named alike and filed together, or
Immich shows a still with no motion and cleanup can leave a clip with nothing to play against.
The link is the folder and the name apart from its extension, which is how Apple exports them;
a pair whose halves were renamed apart is no longer recognisable and is treated as two files.
"""
import os

STILLS = ('.heic', '.heif', '.jpg', '.jpeg')
CLIPS = ('.mov',)


def pairs(paths):
    """{clip: still} for every pair among `paths`. A name with two stills (IMG_1.HEIC and
    IMG_1.JPG) is ambiguous, so it pairs with neither."""
    stills = {}
    for p in paths:
        stem, ext = os.path.splitext(p)
        if ext.lower() in STILLS:
            stills.setdefault(stem.lower(), []).append(p)
    out = {}
    for p in paths:
        stem, ext = os.path.splitext(p)
        if ext.lower() in CLIPS and len(stills.get(stem.lower(), ())) == 1:
            out[p] = stills[stem.lower()][0]
    return out


def partner(path):
    """The other half of `path` on disk, or None. Matched against the folder's real names, so a
    case-insensitive filesystem cannot make IMG_1.mov and IMG_1.MOV look like two files."""
    folder, name = os.path.split(path)
    stem, ext = os.path.splitext(name)
    want = STILLS if ext.lower() in CLIPS else CLIPS if ext.lower() in STILLS else ()
    try:
        names = os.listdir(folder)
    except OSError:
        return None
    found = [n for n in names if os.path.splitext(n)[0].lower() == stem.lower()
             and os.path.splitext(n)[1].lower() in want]
    return os.path.join(folder, found[0]) if len(found) == 1 else None
