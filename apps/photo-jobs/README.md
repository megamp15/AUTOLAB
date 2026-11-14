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
| **Apply** | Makes the ticked moves, nothing else. A move is skipped if its file is gone or its destination now exists. Nothing is overwritten. |
| **Undo** | Every apply is a run in History; undo puts its moved files back, skipping anything that has changed. Deleted files cannot be put back. |

The Inbox and Immich tables scroll inside their own frame. The chips above them are
quick filters (a kind, or Live photos); the checkbox in the header ticks or unticks
everything shown; ticking a row changes only that row.

Where things are put decides what happens to them:

- `_inbox/loose/` each photo and video is dated by ExifTool and filed in `library/YYYY/MM/`.
- `_inbox/events/<folder>` each folder moves whole into the month most of its photos are from (or the month before, if it has at least half as many there).
- `library/YYYY/<folder>` a folder directly in a year is an event too.
- Photos with no recording time go to `_no_date/`; copies of photos already filed go to `_duplicates/` beside the kept copy.
- A **Live Photo** (a HEIC/JPEG and the MOV beside it with the same name) is one photo: dated by the still, named alike, a duplicate only when both halves are, and ticked or unticked together. See `photo_jobs/pairs.py`.

## Duplicates

The Duplicates tab compares byte-identical files across the whole library and keeps the
best copy of each (you can pick another). The extras are **filed** under `_duplicates/`,
which undo reverses, or, if you switch the mode to **Delete**, removed for good.

**Choosing for many groups at once.** The search box narrows the groups shown, and the
controls under it act on exactly those: the checkbox handles or skips every group shown,
**Keep copies there** keeps the copy whose path contains what you typed (say `/Trip/` or
`2025/06/Backup`) in every group shown that has one, and **Reset keepers** goes back to the
best copy of each. A group with no copy there is left as it was.

## Deleting, and what makes it safe

Nothing is deleted unless you switch a plan to **Delete** and type `DELETE` in the
confirmation (the API refuses without `confirm: "DELETE"`). Even then:

- a duplicate is deleted only if it is **still byte-for-byte the copy you are keeping**, checked
  again at the moment of deletion; a missing or changed keeper means nothing is deleted;
- an Immich-trashed file is deleted only if it is **still the exact file Immich trashed**
  (its SHA-1 matches Immich's recorded checksum), and never if it is a symlink;
- a Live Photo half is never deleted while its other half stays;
- every deletion is recorded in History with the SHA-1 the file had, and says it cannot be undone.

## Immich's trash

Immich never deletes the files of a folder it only reads, so photos you delete in Immich
stay on disk. The **Immich trash** tab reads Immich's trash (it needs an API key with the
`asset.read` permission and changes nothing in Immich) and shows each asset with where its
file is in the library: **still on disk**, **not on disk** (already gone), or **in Immich's
own storage** (not this folder, so it is removed by emptying Immich's trash). A Live Photo's
still is shown with its clip, and they are removed together. You can **move** the files to
`_removed/` (undo puts them back) or **delete** them for good.

The path Immich reports (`/mnt/mahir-personal/...`) is mapped to this folder with
`IMMICH_MEDIA_PREFIX`. Both the current Immich search (a `trashedAt` filter) and the older one
(`withDeleted`) are supported.

## Albums

The Albums tab looks for event folders at `library/YYYY/MM/<event>`. It matches the folder's
files to scanned Immich assets by their original path. Applying an Inbox sort automatically
queues a scan when it moves files into the library. For files moved outside Photo Jobs, use
**Scan Immich library** in Albums, then **Refresh matches** after Immich finishes. A folder with
no matching assets stays marked **Scan Immich first**. Immich may treat a moved file as a new
asset and lose the old asset's album membership on rescan. Choose one or many events, edit their
album names if needed, then create the albums. If an album with that name already exists, the app
adds only missing assets. Repeated runs are safe and never remove assets from albums. Live Photo
stills and clips are both added. The Immich API key needs `asset.read`, `album.read`,
`album.create`, `albumAsset.create`, `library.read` and `library.update` permissions. The library
permissions are used only to identify and queue a scan for the configured external library;
Immich requires an admin-owned key for those library endpoints.

## Running it

```sh
# a made-up library (with a stand-in Immich) to click through, on http://127.0.0.1:8099/
python3 apps/photo-jobs/dev/demo.py /tmp/photo-demo 8099
# open http://127.0.0.1:8099/#albums to try the album review/create flow

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
| `IMMICH_URL`, `IMMICH_API_KEY` | the Immich server and a key with `asset.read`, `album.read`, `album.create`, `albumAsset.create`, `library.read` and `library.update` | unset |
| `IMMICH_MEDIA_PREFIX` | where the media folder appears inside Immich's container | `/mnt/mahir-personal` |

Who may reach it is decided in front of it (Traefik and Pocket ID). The token is
a second lock so that reaching the container's port directly gets nothing.

## API

`GET /api/status`, `GET /api/job`, `GET|POST /api/plans`,
`GET|PATCH /api/plans/<id>`, `GET /api/plans/<id>/moves`,
`GET /api/plans/<id>/groups`, `GET /api/plans/<id>/items` (Immich), `GET /api/immich`,
`POST /api/plans/<id>/apply` (a delete plan needs `{"confirm": "DELETE"}`), `GET /api/runs`,
`GET /api/runs/<id>`, `POST /api/runs/<id>/undo`. One job (scan, apply or undo)
runs at a time; a second request gets 409.

## Tests

`python3 -m unittest scripts.test_photo_jobs` runs the real planning, apply,
undo and HTTP code against a throwaway library with `dev/fake_exiftool.py`
standing in for ExifTool (dates from a JSON map) and `dev/fake_immich.py` standing in for
Immich's API.

The link between a Live Photo's halves is the name, not Apple's
ContentIdentifier (which needs real ExifTool to read). A pair renamed apart is
treated as two files.
