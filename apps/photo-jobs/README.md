# Photo Jobs

Plan, review, apply and undo the moves that keep a photo library tidy. A small
Python service (standard library only, plus ExifTool) and one HTML page, in the
design of the AUTOLAB home page. It replaces the old `sort.py` / `dupes.py`
scripts.

## What it does

| Step | |
|---|---|
| **Scan** | Reads the library and produces the exact list of moves. Changes nothing. |
| **Review** | Each move can be unticked, as a kind ("no date"), a pair, an event or a duplicate group. For duplicates, pick which copy to keep. |
| **Apply** | Makes the ticked moves, nothing else. A move is skipped if its file is gone or its destination now exists. Nothing is overwritten or deleted. |
| **Undo** | Every apply is a run in History; undo puts its files back, skipping anything that has changed. |

Where things are put decides what happens to them:

- `_inbox/loose/` each photo and video is dated by ExifTool and filed in `library/YYYY/MM/`.
- `_inbox/events/<folder>` each folder moves whole into the month most of its photos are from (or the month before, if it has at least half as many there).
- `library/YYYY/<folder>` a folder directly in a year is an event too.
- Photos with no recording time go to `_no_date/`; copies of photos already filed go to `_duplicates/` beside the kept copy.
- A **Live Photo** (a HEIC/JPEG and the MOV beside it with the same name) is one photo: dated by the still, named alike, a duplicate only when both halves are, and ticked or unticked together. See `photo_jobs/pairs.py`.

The duplicates tab compares byte-identical files across the whole library. It
never deletes; extra copies are filed under `_duplicates/`.

## Running it

```sh
# a made-up library to click through, on http://127.0.0.1:8099/
python3 apps/photo-jobs/dev/demo.py /tmp/photo-demo 8099

# for real (needs exiftool on PATH)
MEDIA_ROOT=/media STATE_DIR=/state PORT=8099 python3 -m photo_jobs.server
```

| Variable | Meaning | Default |
|---|---|---|
| `MEDIA_ROOT` | the folder holding `library/` and `_inbox/` | `/media` |
| `STATE_DIR` | where plans and run records are kept (JSON files) | `/state` |
| `LIBRARY` | the library folder's name under the media root | `library` |
| `PORT`, `BIND` | where to listen | `8099`, `0.0.0.0` |
| `PHOTO_JOBS_TOKEN` | when set, `/api/*` needs it in `X-Autolab-Photos-Token` | unset |

Who may reach it is decided in front of it (Traefik and Pocket ID). The token is
a second lock so that reaching the container's port directly gets nothing.

## API

`GET /api/status`, `GET /api/job`, `GET|POST /api/plans`,
`GET|PATCH /api/plans/<id>`, `GET /api/plans/<id>/moves`,
`GET /api/plans/<id>/groups`, `POST /api/plans/<id>/apply`, `GET /api/runs`,
`GET /api/runs/<id>`, `POST /api/runs/<id>/undo`. One job (scan, apply or undo)
runs at a time; a second request gets 409.

## Tests

`python3 -m unittest scripts.test_photo_jobs` runs the real planning, apply,
undo and HTTP code against a throwaway library with `dev/fake_exiftool.py`
standing in for ExifTool, which reads dates from a JSON map.

The link between a Live Photo's halves is the name, not Apple's
ContentIdentifier (which needs real ExifTool to read). A pair renamed apart is
treated as two files.
