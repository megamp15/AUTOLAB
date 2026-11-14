#!/usr/bin/env python3
"""Restore missing configured AUTOLAB NFS exports without rewriting UGOS rules."""
import fcntl
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time

EXPORT = '/volume1/autolab'
CONFIG = Path('/etc/exports')
METRIC = Path(os.environ.get('AUTOLAB_NFS_METRIC_DIR', '/volume1/docker/autolab-observability/textfile')) / 'autolab_nfs_exports.prom'
LINE = re.compile(r'^\s*(/\S+)\s+([A-Za-z0-9][A-Za-z0-9.-]*\.ts\.net)\(([^\s()]*)\)\s*(?:#.*)?$')


def configured(text, require=True):
    rules = {}
    for line in text.splitlines():
        match = LINE.fullmatch(line)
        if match and match.group(1) == EXPORT:
            host, options = match.group(2).lower(), match.group(3)
            if host in rules:
                raise ValueError('duplicate NFS client rule')
            rules[host] = options
        elif line.strip().startswith(EXPORT + ' '):
            raise ValueError('unsupported AUTOLAB export rule; refusing changes')
    if require and not rules:
        raise ValueError('no AUTOLAB export rules found; refusing changes')
    return rules


def recover(config_text, active_text, resolve, export):
    rules = configured(config_text)
    active = configured(active_text, require=False)
    missing = [host for host in rules if host not in active]
    if not missing:
        return 0
    # A failed DNS lookup must never replace a rule or trigger a global reload.
    for host in missing:
        resolve(host)
    for host in missing:
        export(host, rules[host])
    return len(missing)


def main():
    METRIC.parent.mkdir(parents=True, exist_ok=True)
    with open('/run/autolab-nfs-export-guard.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ok, repaired = 0, 0
        try:
            active = subprocess.run(['exportfs', '-s'], check=True, text=True, capture_output=True, timeout=15).stdout
            repaired = recover(CONFIG.read_text(), active,
                lambda host: socket.getaddrinfo(host, None, socket.AF_INET),
                lambda host, opts: subprocess.run(['exportfs', '-i', '-o', opts, f'{host}:{EXPORT}'], check=True, timeout=15, capture_output=True))
            after = configured(subprocess.run(['exportfs', '-s'], check=True, text=True, capture_output=True, timeout=15).stdout, require=False)
            if set(configured(CONFIG.read_text())) - set(after):
                raise RuntimeError('configured exports still missing after repair')
            ok = 1
            print(f'autolab NFS exports verified; restored {repaired}')
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            print(f'autolab NFS export check failed: {type(error).__name__}', file=sys.stderr)
        state = METRIC.parent / '.autolab-nfs-export-repairs'
        try:
            repairs = int(state.read_text())
        except FileNotFoundError:
            repairs = 0
        if repaired and ok:
            repairs += repaired
            state.write_text(str(repairs) + '\n')
        fd, tmp = tempfile.mkstemp(dir=METRIC.parent, prefix='.nfs-exports-', text=True)
        with os.fdopen(fd, 'w') as out:
            out.write('# HELP autolab_nfs_exports_ok AUTOLAB NFS exports are active.\n# TYPE autolab_nfs_exports_ok gauge\n')
            out.write(f'autolab_nfs_exports_ok {ok}\n')
            out.write('# HELP autolab_nfs_export_repairs_total Configured NFS exports restored.\n# TYPE autolab_nfs_export_repairs_total counter\n')
            out.write(f'autolab_nfs_export_repairs_total {repairs}\n')
            out.write('# HELP autolab_nfs_exports_checked_timestamp_seconds Last NFS export guard check.\n# TYPE autolab_nfs_exports_checked_timestamp_seconds gauge\n')
            out.write(f'autolab_nfs_exports_checked_timestamp_seconds {int(time.time())}\n')
        os.chmod(tmp, 0o644)
        os.replace(tmp, METRIC)
        return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
