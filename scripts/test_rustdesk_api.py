#!/usr/bin/env python3
"""The RustDesk API server, driven the way the RustDesk client drives it.

Each request body and each response check below is taken from the client's source (see the module
docstring of apps/rustdesk-api/server.py), so a test failing means a real client would misbehave,
not just that a helper changed. Nothing here has run against a real client: that is the README's
"Trying it with the client" step, and the one thing these tests cannot prove.
"""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "apps/rustdesk-api"
sys.path.insert(0, str(APP))
import server  # noqa: E402

PASSWORD = "correct horse battery staple"


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DB_PATH = str(Path(self.tmp.name) / "api.db")
        server.FAILURES = server.Failures()
        conn = server.connect()
        with conn:
            for name, admin in (("alice", 1), ("bob", 0)):
                conn.execute("insert into users (name, pw, is_admin, created) values (?, ?, ?, 0)",
                             (name, server.hash_password(PASSWORD), admin))
        conn.close()
        self.srv = server.make_server("127.0.0.1", 0)
        self.base = "http://127.0.0.1:%d" % self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()

    # --- helpers
    def call(self, method, path, body=None, token=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if token:
            req.add_header("Authorization", "Bearer " + token)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as err:
            return err.code, err.read()

    def post(self, path, body=None, token=None):
        status, raw = self.call("POST", path, body if body is not None else {}, token)
        return status, (json.loads(raw) if raw.strip().startswith((b"{", b"[")) else raw)

    def login(self, name="alice", password=PASSWORD):
        # The body LoginRequest.toJson builds in hbbs.dart: type "account", plus deviceInfo.
        return self.post("/api/login", {"username": name, "password": password, "id": "123456789",
                                         "uuid": "dXVpZA==", "autoLogin": True, "type": "account",
                                         "deviceInfo": {"name": "laptop", "os": "macos", "type": "client"}})

    def token(self, name="alice"):
        status, body = self.login(name)
        self.assertEqual(status, 200)
        return body["access_token"]

    def book(self, token):
        status, raw = self.call("GET", "/api/ab", token=token)
        self.assertEqual(status, 200)
        return json.loads(json.loads(raw)["data"])  # the client json-decodes 'data' a second time

    def sysinfo(self, dev_id, **extra):
        info = {"id": dev_id, "uuid": "u-" + dev_id, "hostname": "PC-" + dev_id, "username": "frontdesk",
                "os": "windows / Windows 11 Pro - 10.0.22631", "version": "1.5.3", "cpu": "x", "memory": "16"}
        info.update(extra)
        return self.post("/api/sysinfo", info)

    # --- signing in
    def test_login_gives_the_token_and_user_the_client_reads(self):
        status, body = self.login()
        self.assertEqual(status, 200)
        self.assertEqual(body["type"], "access_token")  # kAuthResTypeToken
        self.assertGreater(len(body["access_token"]), 30)
        self.assertEqual(body["user"]["name"], "alice")
        self.assertEqual(body["user"]["status"], 1)  # UserPayload: 1 is a normal user
        self.assertTrue(body["user"]["is_admin"])

    def test_wrong_password_and_unknown_user_look_the_same(self):
        a = self.login(password="nope")
        b = self.login(name="nobody")
        self.assertEqual(a, b)
        self.assertEqual(a[0], 401)
        self.assertIn("error", a[1])  # the client shows body['error']

    def test_five_failures_lock_the_account_even_for_the_right_password(self):
        for _ in range(5):
            self.login(password="nope")
        self.assertEqual(self.login()[0], 429)
        self.assertEqual(self.login("bob")[0], 200)  # another account is unaffected

    def test_current_user_needs_a_live_token(self):
        token = self.token()
        status, body = self.post("/api/currentUser", {"id": "1", "uuid": "x"}, token)
        self.assertEqual((status, body["name"]), (200, "alice"))
        self.assertEqual(self.post("/api/currentUser", {})[0], 401)  # 401 is what logs the client out
        self.assertEqual(self.post("/api/currentUser", {}, "x" * 43)[0], 401)

    def test_logout_ends_the_token(self):
        token = self.token()
        self.assertEqual(self.post("/api/logout", {"id": "1", "uuid": "x"}, token)[0], 200)
        self.assertEqual(self.post("/api/currentUser", {}, token)[0], 401)

    def test_login_options_is_an_empty_list(self):
        status, raw = self.call("GET", "/api/login-options")
        self.assertEqual((status, json.loads(raw)), (200, []))

    def test_passwords_and_tokens_are_not_stored_readable(self):
        token = self.token()
        conn = server.connect()
        dump = json.dumps([list(r) for r in conn.execute("select * from users")]
                          + [list(r) for r in conn.execute("select * from tokens")])
        conn.close()
        self.assertNotIn(PASSWORD, dump)
        self.assertNotIn(token, dump)

    # --- address book
    def test_the_client_is_told_to_use_legacy_address_book_mode(self):
        token = self.token()
        self.assertEqual(self.post("/api/ab/personal", {}, token)[0], 404)
        self.assertEqual(self.post("/api/ab/settings", {}, token)[0], 404)

    def test_a_new_book_is_the_shape_the_client_deserializes(self):
        book = self.book(self.token())
        self.assertEqual(set(book), {"tags", "peers", "tag_colors"})
        self.assertIsInstance(book["tag_colors"], str)  # a JSON string inside the JSON

    def test_both_owners_see_one_book(self):
        alice, bob = self.token("alice"), self.token("bob")
        saved = {"tags": ["Smith Dental"], "tag_colors": "{}",
                 "peers": [{"id": "111", "alias": "Front desk", "tags": ["Smith Dental"], "hash": "h"}]}
        status, _ = self.call("POST", "/api/ab", {"data": json.dumps(saved)}, alice)
        self.assertEqual(status, 200)  # an empty 200 is "saved"
        self.assertEqual(self.book(bob)["peers"][0]["alias"], "Front desk")

    def test_a_malformed_book_is_refused_and_changes_nothing(self):
        token = self.token()
        self.call("POST", "/api/ab", {"data": json.dumps({"tags": ["a"], "peers": [], "tag_colors": "{}"})}, token)
        for bad in ({"data": "not json"}, {"data": json.dumps([1])}, {"data": json.dumps({"peers": "x", "tags": []})}, {}):
            self.assertEqual(self.call("POST", "/api/ab", bad, token)[0], 400, bad)
        self.assertEqual(self.book(token)["tags"], ["a"])

    def test_the_book_needs_a_token(self):
        self.assertEqual(self.call("GET", "/api/ab")[0], 401)
        self.assertEqual(self.call("POST", "/api/ab", {"data": "{}"})[0], 401)

    # --- devices listing themselves
    def test_an_unknown_machine_is_asked_for_its_sysinfo(self):
        status, body = self.post("/api/heartbeat", {"id": "555", "uuid": "u-555", "ver": 1005003})
        self.assertEqual((status, body), (200, {"sysinfo": True}))

    def test_sysinfo_lists_the_machine_in_the_shared_book(self):
        status, raw = self.call("POST", "/api/sysinfo", {"id": "555", "uuid": "u-555", "hostname": "SMITH-FRONT",
                                                         "username": "reception", "os": "windows / Windows 11 Pro - 10.0",
                                                         "version": "1.5.3"})
        self.assertEqual((status, raw), (200, b"SYSINFO_UPDATED"))  # the client compares this string
        peer = self.book(self.token("bob"))["peers"][0]
        self.assertEqual((peer["id"], peer["hostname"], peer["username"], peer["platform"]),
                         ("555", "SMITH-FRONT", "reception", "Windows"))
        self.assertEqual(peer["tags"], [server.DEFAULT_TAG])
        self.assertIn(server.DEFAULT_TAG, self.book(self.token("bob"))["tags"])
        self.assertEqual(self.post("/api/heartbeat", {"id": "555", "uuid": "u-555"})[1], {})  # now known

    def test_platforms_use_the_clients_names(self):
        for i, (os_field, expected) in enumerate((("linux / Ubuntu 22.04", "Linux"), ("macos / macOS 14", "Mac OS"),
                                                  ("android / Pixel", "Android"), ("plan9", ""))):
            self.sysinfo("70%d" % i, os=os_field)
        got = {p["id"]: p["platform"] for p in self.book(self.token())["peers"]}
        self.assertEqual(got, {"700": "Linux", "701": "Mac OS", "702": "Android", "703": ""})

    def test_a_reinstall_that_changes_the_uuid_is_asked_again(self):
        self.sysinfo("555")
        self.assertEqual(self.post("/api/heartbeat", {"id": "555", "uuid": "different"})[1], {"sysinfo": True})

    def test_a_refresh_keeps_what_the_owners_set(self):
        self.sysinfo("555")
        token = self.token()
        book = self.book(token)
        book["peers"][0].update(alias="Smith front desk", tags=["Smith Dental"], hash="saved-password")
        book["tags"].append("Smith Dental")
        self.call("POST", "/api/ab", {"data": json.dumps(book)}, token)
        self.sysinfo("555", hostname="SMITH-FRONT-RENAMED")
        peer = self.book(token)["peers"][0]
        self.assertEqual((peer["alias"], peer["tags"], peer["hash"]), ("Smith front desk", ["Smith Dental"], "saved-password"))
        self.assertEqual(peer["hostname"], "SMITH-FRONT-RENAMED")  # the client's own facts do refresh
        self.assertEqual(len(self.book(token)["peers"]), 1)

    def test_a_machine_an_owner_removed_stays_removed(self):
        self.sysinfo("555")
        token = self.token()
        book = self.book(token)
        book["peers"] = []
        self.call("POST", "/api/ab", {"data": json.dumps(book)}, token)
        self.sysinfo("555")
        self.assertEqual(self.book(token)["peers"], [])

    def test_a_client_built_for_a_customer_files_itself_under_that_customer(self):
        self.sysinfo("555", **{"preset-address-book-tag": "Smith Dental", "preset-address-book-alias": "Front desk"})
        book = self.book(self.token())
        self.assertEqual((book["peers"][0]["tags"], book["peers"][0]["alias"]), (["Smith Dental"], "Front desk"))
        self.assertIn("Smith Dental", book["tags"])

    def test_a_hundred_machines_registering_at_once_all_arrive(self):
        errors = []

        def register(n):
            # A connection refused or reset raises here, not a status: record it, because a thread
            # that dies quietly is how this test once passed while a third of the machines were lost.
            try:
                status, _ = self.sysinfo("9%05d" % n)
            except Exception as exc:  # noqa: BLE001
                status = repr(exc)
            if status != 200:
                errors.append(status)

        threads = [threading.Thread(target=register, args=(n,)) for n in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len({p["id"] for p in self.book(self.token())["peers"]}), 100)

    def test_one_machine_registering_twice_at_once_is_listed_once(self):
        # A client posts sysinfo on start and again on the next heartbeat. Both reading "unknown"
        # before either writes is the case the up-front write lock exists for.
        results = []

        def register():
            try:
                results.append(self.sysinfo("555")[0])
            except Exception as exc:  # noqa: BLE001
                results.append(repr(exc))

        threads = [threading.Thread(target=register) for _ in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(set(results), {200})
        self.assertEqual([p["id"] for p in self.book(self.token())["peers"]], ["555"])

    def test_sysinfo_without_an_id_is_refused(self):
        self.assertEqual(self.post("/api/sysinfo", {"hostname": "x"})[0], 400)

    def test_sysinfo_ver_says_not_supported(self):
        # Any 2xx would make the client believe it is talking to RustDesk's paid server.
        self.assertEqual(self.post("/api/sysinfo_ver", {})[0], 404)

    # --- audit
    def test_connection_audit_posts_are_kept(self):
        body = {"id": "555", "uuid": "u", "conn_id": 7, "session_id": 1, "nonce": "n", "action": "new", "ip": "100.64.0.9"}
        self.assertEqual(self.call("POST", "/api/audit/conn", body)[0], 200)
        conn = server.connect()
        rows = [(r["kind"], json.loads(r["body"])["action"]) for r in conn.execute("select * from audit")]
        conn.close()
        self.assertEqual(rows, [("conn", "new")])

    # --- bad input
    def test_malformed_and_oversized_bodies_are_400_not_a_crash(self):
        self.assertEqual(self.call("POST", "/api/login", raw=b"{nope")[0], 400)
        self.assertEqual(self.call("POST", "/api/login", raw=b"[1, 2]")[0], 400)
        server.MAX_BODY = 10
        try:
            self.assertEqual(self.call("POST", "/api/login", raw=b'{"username": "aaaaaaaaaaaaaaaa"}')[0], 400)
        finally:
            server.MAX_BODY = 5 * 1024 * 1024
        self.assertEqual(self.call("GET", "/api/nothing")[0], 404)


class CommandLineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DB_PATH = str(Path(self.tmp.name) / "cli.db")
        os.environ["RUSTDESK_API_PASSWORD"] = PASSWORD

    def tearDown(self):
        os.environ.pop("RUSTDESK_API_PASSWORD", None)
        self.tmp.cleanup()

    def test_add_a_user_who_can_then_sign_in_and_a_short_password_is_refused(self):
        server.main(["user", "add", "carol"])
        conn = server.connect()
        row = conn.execute("select * from users where name = 'carol'").fetchone()
        conn.close()
        self.assertTrue(server.check_password(row["pw"], PASSWORD))
        self.assertFalse(server.check_password(row["pw"], "wrong"))
        os.environ["RUSTDESK_API_PASSWORD"] = "short"
        with self.assertRaises(SystemExit):
            server.main(["user", "add", "dave"])

    def test_changing_a_password_signs_the_user_out_everywhere(self):
        server.main(["user", "add", "carol"])
        conn = server.connect()
        with conn:
            conn.execute("insert into tokens (hash, user, created, last_used) values ('h', 'carol', 0, 0)")
        conn.close()
        os.environ["RUSTDESK_API_PASSWORD"] = "a different long password"
        server.main(["user", "passwd", "carol"])
        conn = server.connect()
        self.assertEqual(conn.execute("select count(*) from tokens").fetchone()[0], 0)
        conn.close()


if __name__ == "__main__":
    unittest.main()
