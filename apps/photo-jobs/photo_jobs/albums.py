"""Match event folders already in the library to Immich albums.

This only reads the external-library files and adds their existing Immich asset IDs to albums.
It never moves, edits, trashes, or deletes a photo.
"""
from collections import Counter
from pathlib import Path, PurePosixPath


def _display(folder):
    return folder.replace('_', ' ').strip()


def _events(cfg):
    library = Path(cfg.root) / cfg.library
    found = []
    try:
        years = sorted(p for p in library.iterdir() if p.is_dir() and not p.is_symlink() and len(p.name) == 4 and p.name.isdigit())
    except FileNotFoundError:
        return found
    for year in years:
        for month in sorted(year.iterdir()):
            if not month.is_dir() or month.is_symlink() or len(month.name) != 2 or not month.name.isdigit():
                continue
            for folder in sorted(month.iterdir()):
                if not folder.is_dir() or folder.is_symlink() or folder.name.startswith('.'):
                    continue
                rel = folder.relative_to(library).as_posix()
                found.append({'path': rel, 'year': year.name, 'month': month.name, 'folder': folder.name,
                              'title': _display(folder.name), 'immich_path':
                              str(Path(cfg.immich_prefix) / cfg.library / rel)})
    counts = Counter((e['year'], e['title'].casefold()) for e in found)
    for event in found:
        event['name'] = (f"{event['year']}-{event['month']} · {event['title']}"
                         if counts[(event['year'], event['title'].casefold())] > 1 else event['title'])
    return found


def _library_assets(cfg, immich, events):
    """Read Immich's scanned assets once and assign them to their exact event folders."""
    root = str(Path(cfg.immich_prefix) / cfg.library).rstrip('/') + '/'
    assets = [a for a in immich.search_assets({'originalPath': {'startsWith': root}})
              if str(a.get('originalPath', '')).startswith(root)]
    by_event = {event['path']: [] for event in events}
    for asset in assets:
        path = str(asset.get('originalPath', ''))
        for event in events:
            prefix = event['immich_path'].rstrip('/') + '/'
            if path.startswith(prefix):
                by_event[event['path']].append(asset)
                break
    return by_event


def scan_external_library(cfg, immich):
    """Queue a scan for the one Immich library containing this app's media path."""
    target = PurePosixPath(cfg.immich_prefix) / cfg.library
    matches = {}
    for library in immich.libraries():
        for import_path in library.get('importPaths', []):
            path = PurePosixPath(str(import_path))
            if path == target or target.is_relative_to(path):
                matches[library.get('id')] = library
                break
    if len(matches) != 1:
        raise ValueError('could not identify exactly one Immich external library for '
                         f'{target}; found {len(matches)} matching libraries')
    library = next(iter(matches.values()))
    immich.scan_library(library['id'])
    return {'id': library['id'], 'name': library.get('name') or str(target)}


def review(cfg, immich):
    """Freshly compare every month/event folder with existing assets and albums."""
    events = _events(cfg)
    by_event = _library_assets(cfg, immich, events)
    albums = immich.albums()
    by_name = {a.get('albumName'): a for a in albums}
    output = []
    for event in events:
        assets = by_event[event['path']]
        album = by_name.get(event['name'])
        member_ids = {a.get('id') for a in immich.album_assets(album['id'])} if album else set()
        missing = [a for a in assets if a.get('id') not in member_ids]
        status = 'not_scanned' if not assets else 'ready' if not album else 'add' if missing else 'current'
        output.append({'path': event['path'], 'name': event['name'], 'folder': event['folder'],
                       'year': event['year'], 'photos': len(assets), 'to_add': len(missing),
                       'album_id': album.get('id') if album else None, 'status': status})
    return output


def create(cfg, immich, requested):
    """Create selected albums or add newly scanned assets to existing ones.

    Re-scan event folders and album membership immediately before writing. The operation is
    additive: it never removes assets from an album.
    """
    current = {e['path']: e for e in _events(cfg)}
    by_event = _library_assets(cfg, immich, list(current.values()))
    albums = immich.albums()
    by_name = {a.get('albumName'): a for a in albums}
    results = []
    for choice in requested:
        path = str(choice.get('path', ''))
        event = current.get(path)
        if not event:
            results.append({'path': path, 'status': 'skipped', 'message': 'event folder changed; scan again'})
            continue
        assets = by_event[path]
        if not assets:
            results.append({'path': path, 'name': choice.get('name') or event['name'], 'status': 'not_scanned', 'photos': 0})
            continue
        name = str(choice.get('name') or event['name']).strip()
        if not name or len(name) > 128:
            raise ValueError('album names must be between 1 and 128 characters')
        album = by_name.get(name)
        if album:
            member_ids = {a.get('id') for a in immich.album_assets(album['id'])}
            missing = [a['id'] for a in assets if a.get('id') not in member_ids]
            if missing:
                immich.add_album_assets(album['id'], missing)
            results.append({'path': path, 'name': name, 'status': 'added' if missing else 'current',
                            'photos': len(assets), 'added': len(missing)})
        else:
            created = immich.create_album(name, [a['id'] for a in assets])
            results.append({'path': path, 'name': name, 'status': 'created', 'photos': len(assets), 'added': len(assets)})
            by_name[name] = created
    return {'results': results}
