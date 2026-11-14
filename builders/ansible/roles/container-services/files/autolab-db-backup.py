#!/usr/bin/env python3
"""Nightly dumps of every app database to the NAS, and a restore that proves them.

    autolab-db-backup dump                 dump each database, check the archive, prune
    autolab-db-backup restore-test [name]  restore the newest dump into a scratch
                                           database and compare it with the live one

The live databases stay on this machine's local disk, where Postgres needs
them; the NAS holds the copies, so the VM can be lost without losing the apps.
A dump nobody has restored is a hope, so the restore test is the half that
matters: it starts a throwaway container of the same image, restores into an
empty database, and requires the same tables as production.

Settings come from /etc/autolab/db-backup.json, written by the
container-services role. Results are written as metrics for the textfile
collector, from the files on the NAS and a small state file, so the alert
rules judge what is actually there and not what a run claimed.
"""
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import time

CONFIG = pathlib.Path(os.environ.get("AUTOLAB_DB_BACKUP_CONFIG", "/etc/autolab/db-backup.json"))
STAMP = "%Y%m%dT%H%M%SZ"
TABLES = ("select count(*) from information_schema.tables "
          "where table_schema not in ('pg_catalog', 'information_schema')")


def log(message):
    print(f"db-backup: {message}", flush=True)


def run(argv, **kwargs):
    return subprocess.run(argv, check=True, text=True, capture_output=True, **kwargs)


def psql(container, user, db, sql):
    return run(["docker", "exec", container, "psql", "-U", user, "-d", db, "-tAc", sql]).stdout.strip()


def newest_dump(folder):
    dumps = sorted(list(folder.glob("*.dump")) + list(folder.glob("*.sql")))
    return dumps[-1] if dumps else None


def maria(db):
    return db.get("kind") == "mariadb"


# MariaDB is dumped and restored by the container's own client, with the
# account its own environment already names; no password crosses this script.
MARIA_DUMP = 'exec mariadb-dump --single-transaction --routines -u"$MARIADB_USER" -p"$MARIADB_PASSWORD" "$MARIADB_DATABASE"'
MARIA_TABLES = ("select count(*) from information_schema.tables where table_schema='{db}'")


def dump_one(cfg, db):
    folder = pathlib.Path(cfg["dest"]) / db["service"]
    folder.mkdir(parents=True, exist_ok=True)
    suffix = "sql" if maria(db) else "dump"
    final = folder / f"{db['service']}-{dt.datetime.now(dt.timezone.utc).strftime(STAMP)}.{suffix}"
    partial = folder / (final.name + ".partial")
    try:
        dump_cmd = (["docker", "exec", db["container"], "sh", "-c", MARIA_DUMP] if maria(db) else
                    ["docker", "exec", db["container"], "pg_dump", "-U", db["user"], "-Fc", db["db"]])
        with partial.open("wb") as out:
            subprocess.run(dump_cmd, check=True, stdout=out, stderr=subprocess.PIPE)
        if partial.stat().st_size == 0:
            raise RuntimeError("the dump is empty")
        if maria(db):
            # mariadb-dump ends a complete dump with a marker line; a cut-off one does not.
            tail = partial.read_bytes()[-200:]
            if b"-- Dump completed" not in tail or b"CREATE TABLE" not in partial.read_bytes():
                raise RuntimeError("the dump is incomplete or has no tables")
        else:
            # The table of contents is read back from the file: a truncated or
            # corrupt archive fails here, tonight, not on the day it is needed.
            with partial.open("rb") as src:
                listing = subprocess.run(["docker", "exec", "-i", db["container"], "pg_restore", "--list"],
                                         check=True, stdin=src, capture_output=True, text=True).stdout
            if " TABLE " not in listing:
                raise RuntimeError("the archive lists no tables")
        os.replace(partial, final)
    finally:
        partial.unlink(missing_ok=True)
    log(f"{db['service']}: {final.name} ({final.stat().st_size} bytes)")


def prune(cfg, service):
    """Newest keep_daily dumps, plus one per week (Sunday's) for keep_weekly_days."""
    folder = pathlib.Path(cfg["dest"]) / service
    now = time.time()
    dumps = sorted(list(folder.glob("*.dump")) + list(folder.glob("*.sql")))
    for path in dumps[:-cfg["keep_daily"]]:
        age_days = (now - path.stat().st_mtime) / 86400
        sunday = dt.datetime.strptime(path.stem.rsplit("-", 1)[1], STAMP).weekday() == 6
        if not (sunday and age_days <= cfg["keep_weekly_days"]):
            path.unlink()
            log(f"{service}: pruned {path.name}")


def restore_test(cfg, db, state):
    name = f"autolab-restore-test-{db['service']}"
    folder = pathlib.Path(cfg["dest"]) / db["service"]
    dump = newest_dump(folder)
    result = {"ok": False, "at": time.time()}
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    try:
        if dump is None:
            raise RuntimeError("there is no dump to restore")
        if maria(db):
            run(["docker", "run", "-d", "--rm", "--name", name, "--memory", "768m", "-e", "MARIADB_ROOT_PASSWORD=restore-test",
                 "-e", f"MARIADB_DATABASE={db['db']}", db["image"]])
            for _ in range(90):
                if subprocess.run(["docker", "exec", name, "healthcheck.sh", "--connect", "--innodb_initialized"],
                                  capture_output=True).returncode == 0:
                    break
                time.sleep(2)
            else:
                raise RuntimeError("the scratch database never came up")
            with dump.open("rb") as src:
                restored = subprocess.run(["docker", "exec", "-i", name, "sh", "-c", 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE"'],
                                          stdin=src, capture_output=True, text=True)
            if restored.returncode != 0:
                raise RuntimeError("the restore failed: " + restored.stderr.strip()[:300])
            count = lambda c, sql: int(run(["docker", "exec", c, "sh", "-c", f'exec mariadb -N -B -uroot -p"$MARIADB_ROOT_PASSWORD" -e "{sql}"']).stdout.strip())
            sql = MARIA_TABLES.format(db=db["db"])
            got, live = count(name, sql), count(db["container"], sql)
        else:
            run(["docker", "run", "-d", "--rm", "--name", name, "--memory", "768m",
                 "-e", "POSTGRES_PASSWORD=restore-test", "-e", f"POSTGRES_USER={db['user']}", "-e", "POSTGRES_DB=postgres",
                 db["image"]])
            # TCP, not the socket: the image's first server runs on the socket
            # alone while it initialises, and only the real one answers on TCP.
            for _ in range(60):
                if subprocess.run(["docker", "exec", name, "pg_isready", "-q", "-h", "127.0.0.1"]).returncode == 0:
                    break
                time.sleep(2)
            else:
                raise RuntimeError("the scratch database never came up")
            run(["docker", "exec", name, "createdb", "-U", db["user"], "--template", "template0", db["db"]])
            with dump.open("rb") as src:
                restored = subprocess.run(
                    ["docker", "exec", "-i", name, "pg_restore", "-U", db["user"], "-d", db["db"], "--no-owner", "--exit-on-error"],
                    stdin=src, capture_output=True, text=True)
            if restored.returncode != 0:
                raise RuntimeError("pg_restore failed: " + restored.stderr.strip()[:300])
            got = int(psql(name, db["user"], db["db"], TABLES))
            live = int(psql(db["container"], db["user"], db["db"], TABLES))
        if got == 0 or got != live:
            raise RuntimeError(f"restored {got} tables, production has {live}")
        result.update(ok=True, tables=got, dump=dump.name)
        log(f"{db['service']}: restore of {dump.name} matches production ({got} tables)")
    except Exception as error:  # reported, then recorded as a failed test
        result["error"] = str(error)
        log(f"{db['service']}: RESTORE TEST FAILED: {error}")
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    state[db["service"]] = result


def write_metrics(cfg, state):
    lines = [
        "# HELP autolab_db_dump_last_success_timestamp_seconds Newest verified dump of an app database on the NAS.",
        "# TYPE autolab_db_dump_last_success_timestamp_seconds gauge",
        "# HELP autolab_db_dump_size_bytes Size of that dump.",
        "# TYPE autolab_db_dump_size_bytes gauge",
        "# HELP autolab_db_restore_test_ok 1 when the last restore matched production, else 0.",
        "# TYPE autolab_db_restore_test_ok gauge",
        "# HELP autolab_db_restore_test_last_timestamp_seconds When the restore test last ran.",
        "# TYPE autolab_db_restore_test_last_timestamp_seconds gauge",
    ]
    for db in cfg["databases"]:
        label = f'service="{db["service"]}"'
        dump = newest_dump(pathlib.Path(cfg["dest"]) / db["service"])
        if dump is not None:
            lines.append(f"autolab_db_dump_last_success_timestamp_seconds{{{label}}} {dump.stat().st_mtime:.0f}")
            lines.append(f"autolab_db_dump_size_bytes{{{label}}} {dump.stat().st_size}")
        test = state.get(db["service"])
        if test:
            lines.append(f"autolab_db_restore_test_ok{{{label}}} {1 if test['ok'] else 0}")
            lines.append(f"autolab_db_restore_test_last_timestamp_seconds{{{label}}} {test['at']:.0f}")
    target = pathlib.Path(cfg["textfile"])
    partial = target.with_suffix(".tmp")
    partial.write_text("\n".join(lines) + "\n")
    os.replace(partial, target)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("dump", "restore-test"):
        sys.exit(__doc__)
    cfg = json.loads(CONFIG.read_text())
    if not os.path.ismount(cfg["mount"]):
        # Writing into an unmounted directory would fill the local disk and
        # back up nothing. Fail loudly; the stale-dump alert follows.
        sys.exit(f"db-backup: {cfg['mount']} is not mounted; is the NAS up?")
    state_path = pathlib.Path(cfg["state"])
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    wanted = [d for d in cfg["databases"] if len(sys.argv) < 3 or d["service"] == sys.argv[2]]
    failed = []
    for db in wanted:
        try:
            if sys.argv[1] == "dump":
                dump_one(cfg, db)
                prune(cfg, db["service"])
            else:
                restore_test(cfg, db, state)
                if not state[db["service"]]["ok"]:
                    failed.append(db["service"])
        except Exception as error:
            log(f"{db['service']}: FAILED: {error}")
            failed.append(db["service"])
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state))
    write_metrics(cfg, state)
    if failed:
        sys.exit(f"db-backup: failed for {', '.join(failed)}")


if __name__ == "__main__":
    main()
