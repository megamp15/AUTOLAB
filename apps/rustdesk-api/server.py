#!/usr/bin/env python3
"""A small RustDesk API server: sign-in, one shared address book, devices that list themselves.

The RustDesk client talks to an "API server" for three things the free ID/relay server does not do:

  * sign in      POST /api/login, /api/currentUser, /api/logout, GET /api/login-options
  * address book GET and POST /api/ab (the client's "legacy" mode: the whole book is one JSON
                 document). Answering 404 to /api/ab/personal and /api/ab/settings is what tells the
                 client to use it, and keeps this server to one table instead of a per-peer API.
  * devices      POST /api/heartbeat and /api/sysinfo, sent by every client that has this server's
                 address. A machine seen for the first time is added to the shared book, so the
                 owners do not type in a hundred IDs.

Plus /api/audit/{conn,file,alarm}, which the client posts when someone connects; they are kept.

Everything here comes from reading the client's source (flutter/lib/models/user_model.dart,
ab_model.dart, src/hbbs_http/sync.rs, src/common.rs), not from another server's behaviour. The
client is the specification, so a client release can change it; scripts/test_rustdesk_api.py pins
what was read, and the client version it was read from is in the README.

Standard library only. Two or three people sign in; this is not built for more.

    server.py serve                        run (RUSTDESK_API_PORT, default 21114; RUSTDESK_API_DB)
    server.py user add NAME [--admin]      password from RUSTDESK_API_PASSWORD or a prompt
    server.py user list | remove NAME | passwd NAME
    server.py devices | audit [-n 20]
"""
import argparse
import base64
import getpass
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_PATH = os.environ.get("RUSTDESK_API_DB", "/data/rustdesk-api.db")
# A machine nobody has sorted yet carries this tag, so a new install is easy to find in the book.
DEFAULT_TAG = os.environ.get("RUSTDESK_API_DEFAULT_TAG", "new")
TOKEN_IDLE_SECONDS = 30 * 24 * 3600
MAX_BODY = 5 * 1024 * 1024
# Failed sign-ins allowed per account before it is refused for a while.
MAX_FAILURES = 5
LOCKOUT_SECONDS = 300

EMPTY_BOOK = {"tags": [], "peers": [], "tag_colors": "{}"}
# The client's own names for a peer's platform; anything else shows no icon.
PLATFORMS = {"windows": "Windows", "linux": "Linux", "macos": "Mac OS", "android": "Android"}

SCHEMA = """
create table if not exists users (
  name text primary key, pw text not null, is_admin integer not null default 0, created real not null);
create table if not exists tokens (
  hash text primary key, user text not null references users(name) on delete cascade,
  created real not null, last_used real not null);
create table if not exists book (id integer primary key check (id = 1), data text not null);
create table if not exists devices (
  id text primary key, uuid text not null, hostname text, username text, os text, version text,
  first_seen real not null, last_seen real not null);
create table if not exists audit (ts real not null, kind text not null, body text not null);
"""


# --- storage -----------------------------------------------------------------------------------

def connect(path=None, init=True):
    conn = sqlite3.connect(path or DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    if init:  # once at start, not on every request
        conn.execute("pragma journal_mode = wal")
        conn.executescript(SCHEMA)
    return conn


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1)
    return "scrypt$%s$%s" % (base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def check_password(stored, password):
    try:
        scheme, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=2 ** 14, r=8, p=1)
        return hmac.compare_digest(calc, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def user_json(row):
    # Only the fields the client reads (UserPayload in hbbs.dart). status 1 is "normal".
    return {"name": row["name"], "display_name": "", "avatar": "", "email": "", "note": "",
            "status": 1, "is_admin": bool(row["is_admin"])}


def load_book(conn):
    row = conn.execute("select data from book where id = 1").fetchone()
    return json.loads(row["data"]) if row else dict(EMPTY_BOOK, tags=[], peers=[])


def save_book(conn, book):
    conn.execute("insert into book (id, data) values (1, ?) on conflict (id) do update set data = excluded.data",
                 (json.dumps(book),))


def platform_of(os_field):
    # "windows / Windows 11 Pro - 10.0.22631" or "linux / Ubuntu 22.04": the part before the slash.
    return PLATFORMS.get((os_field or "").split(" / ")[0].strip().lower(), "")


def register_device(conn, info):
    """Record what a client reports about itself, and list it in the book if it is new.

    The book is the owners' to edit: a known machine only has the facts the client owns
    (hostname, login name, platform) refreshed, never its alias, tags or saved password.
    """
    now = time.time()
    dev_id, uuid = str(info["id"]), str(info["uuid"])
    known = conn.execute("select 1 from devices where id = ?", (dev_id,)).fetchone()
    conn.execute(
        "insert into devices (id, uuid, hostname, username, os, version, first_seen, last_seen) "
        "values (?, ?, ?, ?, ?, ?, ?, ?) on conflict (id) do update set uuid = excluded.uuid, "
        "hostname = excluded.hostname, username = excluded.username, os = excluded.os, "
        "version = excluded.version, last_seen = excluded.last_seen",
        (dev_id, uuid, info.get("hostname", ""), info.get("username", ""), info.get("os", ""),
         info.get("version", ""), now, now))
    book = load_book(conn)
    peers = {p.get("id"): p for p in book["peers"]}
    facts = {"hostname": info.get("hostname", ""), "username": info.get("username", ""),
             "platform": platform_of(info.get("os"))}
    if dev_id in peers:
        peers[dev_id].update(facts)
    elif not known:
        # A client built with presets says which customer it belongs to (preset-address-book-*).
        tag = info.get("preset-address-book-tag") or DEFAULT_TAG
        peer = dict(facts, id=dev_id, alias=info.get("preset-address-book-alias", ""), tags=[tag], hash="")
        book["peers"].append(peer)
        if tag and tag not in book["tags"]:
            book["tags"].append(tag)
    else:
        # Known to the server, absent from the book: an owner removed it. It stays removed.
        return
    save_book(conn, book)


# --- request handling --------------------------------------------------------------------------

class Failures:
    """Failed sign-ins by account, in memory: a restart forgives them, which is fine."""

    def __init__(self):
        self.lock = threading.Lock()
        self.seen = {}

    def blocked(self, *keys):
        now = time.time()
        with self.lock:
            return any(len([t for t in self.seen.get(k, []) if now - t < LOCKOUT_SECONDS]) >= MAX_FAILURES
                       for k in keys)

    def add(self, *keys):
        now = time.time()
        with self.lock:
            for k in keys:
                self.seen[k] = [t for t in self.seen.get(k, []) if now - t < LOCKOUT_SECONDS] + [now]

    def clear(self, *keys):
        with self.lock:
            for k in keys:
                self.seen.pop(k, None)


class Handler(BaseHTTPRequestHandler):
    server_version = "rustdesk-api"
    protocol_version = "HTTP/1.1"

    # --- plumbing
    def log_message(self, fmt, *args):  # never the body: it can hold a password
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def send(self, status, body=b"", content_type="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def error(self, status, message):
        self.send(status, {"error": message})

    def body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            raise ValueError("body size")
        raw = self.rfile.read(length) if length else b""
        return json.loads(raw) if raw.strip() else {}

    def user(self, conn):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or len(auth) < 20:
            return None
        h, now = token_hash(auth[7:]), time.time()
        row = conn.execute("select u.* from tokens t join users u on u.name = t.user "
                           "where t.hash = ? and t.last_used > ?", (h, now - TOKEN_IDLE_SECONDS)).fetchone()
        if row:
            conn.execute("update tokens set last_used = ? where hash = ?", (now, h))
        return row

    def route(self, method):
        path = self.path.split("?", 1)[0].rstrip("/")
        handler = ROUTES.get((method, path))
        if handler is None and method == "POST" and path.startswith("/api/audit/"):
            handler = audit
        if handler is None:
            return self.error(404, "not found")
        try:
            payload = self.body() if method == "POST" else {}
        except (ValueError, json.JSONDecodeError):
            return self.error(400, "bad request")
        if not isinstance(payload, dict):
            return self.error(400, "bad request")
        conn = connect(init=False)
        try:
            with conn:
                # The write lock from the first statement, so correctness does not depend on which
                # line of a handler writes first. (register_device happens to take it early anyway,
                # and no test can tell the two apart; this is for whoever edits it next.)
                conn.execute("begin immediate")
                reply = handler(self, conn, payload)
            # Sent after the commit, never before: a client told "saved" may read straight away.
            self.send(*reply)
        finally:
            conn.close()

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")


FAILURES = Failures()


def err(status, message):
    return status, {"error": message}


def login(h, conn, p):
    name, password = str(p.get("username", "")), str(p.get("password", ""))
    # By account only: behind the ingress every request arrives from one address, so counting
    # addresses would lock everybody out after one person's typos.
    keys = ("user:" + name,)
    if FAILURES.blocked(*keys):
        return err(429, "Too many attempts, try again in a few minutes")
    row = conn.execute("select * from users where name = ?", (name,)).fetchone()
    # Hash even for an unknown name, so a missing account and a wrong password take the same time.
    stored = row["pw"] if row else hash_password("x")
    if not (check_password(stored, password) and row):
        FAILURES.add(*keys)
        return err(401, "Wrong username or password")
    FAILURES.clear(*keys)
    token, now = secrets.token_urlsafe(32), time.time()
    conn.execute("insert into tokens (hash, user, created, last_used) values (?, ?, ?, ?)",
                 (token_hash(token), name, now, now))
    return 200, {"type": "access_token", "access_token": token, "user": user_json(row)}


def current_user(h, conn, p):
    row = h.user(conn)
    return (200, user_json(row)) if row else err(401, "Not signed in")


def logout(h, conn, p):
    auth = h.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        conn.execute("delete from tokens where hash = ?", (token_hash(auth[7:]),))
    return 200, {}


def login_options(h, conn, p):
    return 200, []  # no third-party sign-in


def not_supported(h, conn, p):
    # 404 here is the client's cue for "legacy address book": see the module docstring.
    return err(404, "not supported")


def get_book(h, conn, p):
    if not h.user(conn):
        return err(401, "Not signed in")
    return 200, {"data": json.dumps(load_book(conn))}


def put_book(h, conn, p):
    if not h.user(conn):
        return err(401, "Not signed in")
    try:
        book = json.loads(p.get("data", ""))
        assert isinstance(book, dict) and isinstance(book.get("peers"), list) and isinstance(book.get("tags"), list)
    except (ValueError, TypeError, AssertionError):
        return err(400, "bad address book")
    book.setdefault("tag_colors", "{}")
    save_book(conn, book)
    return 200, b""  # an empty 200 is the client's "saved"


def heartbeat(h, conn, p):
    dev = conn.execute("select uuid from devices where id = ?", (str(p.get("id", "")),)).fetchone()
    # Not seen before, or its uuid changed (a reinstall that kept the ID): ask for its sysinfo.
    if not dev or dev["uuid"] != str(p.get("uuid", "")):
        return 200, {"sysinfo": True}
    conn.execute("update devices set last_seen = ? where id = ?", (time.time(), str(p["id"])))
    return 200, {}


def sysinfo(h, conn, p):
    if not p.get("id") or not p.get("uuid"):
        return err(400, "id and uuid are required")
    register_device(conn, p)
    return 200, b"SYSINFO_UPDATED", "text/plain"  # the client checks for exactly this string


def sysinfo_ver(h, conn, p):
    # Any 2xx here makes the client treat the server as RustDesk's own paid one; 404 keeps it plain.
    return err(404, "not supported")


def audit(h, conn, p):
    kind = h.path.split("?", 1)[0].rstrip("/").rsplit("/", 1)[1]
    conn.execute("insert into audit (ts, kind, body) values (?, ?, ?)", (time.time(), kind, json.dumps(p)))
    return 200, b""


ROUTES = {
    ("POST", "/api/login"): login,
    ("POST", "/api/currentUser"): current_user,
    ("POST", "/api/logout"): logout,
    ("GET", "/api/login-options"): login_options,
    ("POST", "/api/ab/personal"): not_supported,
    ("POST", "/api/ab/settings"): not_supported,
    ("GET", "/api/ab"): get_book,
    ("POST", "/api/ab"): put_book,
    ("POST", "/api/heartbeat"): heartbeat,
    ("POST", "/api/sysinfo"): sysinfo,
    ("POST", "/api/sysinfo_ver"): sysinfo_ver,
}


class Server(ThreadingHTTPServer):
    # The default backlog is 5. After a power cut or a restart every machine reconnects in the same
    # second, and the kernel resets the connections that do not fit; clients retry, but a server
    # that drops a hundred clients' first attempt is not one to trust with the 101st.
    request_queue_size = 128
    daemon_threads = True


def make_server(host, port):
    connect().close()
    return Server((host, port), Handler)


# --- command line ------------------------------------------------------------------------------

def read_password(confirm):
    if os.environ.get("RUSTDESK_API_PASSWORD"):
        return os.environ["RUSTDESK_API_PASSWORD"]
    password = getpass.getpass("Password: ")
    if confirm and getpass.getpass("Again: ") != password:
        sys.exit("The two passwords differ.")
    return password


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("serve")
    user = sub.add_parser("user").add_subparsers(dest="action", required=True)
    add = user.add_parser("add")
    add.add_argument("name")
    add.add_argument("--admin", action="store_true")
    user.add_parser("list")
    for action in ("remove", "passwd"):
        user.add_parser(action).add_argument("name")
    sub.add_parser("devices")
    audit_cmd = sub.add_parser("audit")
    audit_cmd.add_argument("-n", type=int, default=20)
    args = ap.parse_args(argv)

    conn = connect()
    if args.cmd in (None, "serve"):
        port = int(os.environ.get("RUSTDESK_API_PORT", "21114"))
        srv = make_server(os.environ.get("RUSTDESK_API_HOST", "0.0.0.0"), port)
        sys.stderr.write("rustdesk-api listening on %s\n" % port)
        srv.serve_forever()
    elif args.cmd == "user":
        with conn:
            if args.action == "add":
                password = read_password(confirm=True)
                if len(password) < 12:
                    sys.exit("Use at least 12 characters.")
                conn.execute("insert into users (name, pw, is_admin, created) values (?, ?, ?, ?)",
                             (args.name, hash_password(password), int(args.admin), time.time()))
            elif args.action == "passwd":
                password = read_password(confirm=True)
                if len(password) < 12:
                    sys.exit("Use at least 12 characters.")
                cur = conn.execute("update users set pw = ? where name = ?", (hash_password(password), args.name))
                if not cur.rowcount:
                    sys.exit("No such user.")
                conn.execute("delete from tokens where user = ?", (args.name,))  # sign them out everywhere
            elif args.action == "remove":
                conn.execute("delete from users where name = ?", (args.name,))
            else:
                for row in conn.execute("select name, is_admin from users order by name"):
                    print(row["name"], "(admin)" if row["is_admin"] else "")
    elif args.cmd == "devices":
        for row in conn.execute("select * from devices order by last_seen desc"):
            print(row["id"], row["hostname"], row["username"], row["os"], row["version"],
                  time.strftime("%Y-%m-%d %H:%M", time.localtime(row["last_seen"])), sep="\t")
    elif args.cmd == "audit":
        for row in conn.execute("select * from audit order by ts desc limit ?", (args.n,)):
            print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row["ts"])), row["kind"], row["body"], sep="\t")


if __name__ == "__main__":
    main()
