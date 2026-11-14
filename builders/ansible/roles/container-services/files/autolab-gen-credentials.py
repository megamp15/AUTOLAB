#!/usr/bin/env python3
"""Generate a service's secrets once, into root-only env files.

Reads a spec on stdin: {"files": [{"path": "...", "lines": ["KEY=value", ...]}]}.
In a value, {PW} is one random password shared by every file in the spec (the
database's and the app's must agree), and {HEX16} {HEX32} {HEX64} {APPKEY} are
fresh each time they appear ({APPKEY} is the `base64:` key Laravel wants).
Every file is written before any is moved into place, and the last file is the
marker Ansible's `creates` looks for, so an interrupted run leaves nothing that
looks finished.
"""
import base64
import json
import os
import secrets
import sys
import tempfile


def render(line, pw):
    out = line.replace("{PW}", pw)
    for token, make in (("{HEX16}", lambda: secrets.token_hex(16)), ("{HEX32}", lambda: secrets.token_hex(32)),
                        ("{HEX64}", lambda: secrets.token_hex(64)),
                        ("{APPKEY}", lambda: "base64:" + base64.b64encode(secrets.token_bytes(32)).decode())):
        while token in out:
            out = out.replace(token, make(), 1)
    return out


def main():
    spec = json.load(sys.stdin)
    pw = secrets.token_hex(24)
    os.umask(0o077)
    staged = []
    try:
        for entry in spec["files"]:
            directory = os.path.dirname(entry["path"])
            fd, temp = tempfile.mkstemp(dir=directory, prefix=".gen.")
            with os.fdopen(fd, "w") as out:
                out.write("\n".join(render(line, pw) for line in entry["lines"]) + "\n")
            staged.append((temp, entry["path"]))
        for temp, path in staged:
            os.replace(temp, path)
        staged = []
    finally:
        for temp, _ in staged:
            os.unlink(temp)


if __name__ == "__main__":
    main()
