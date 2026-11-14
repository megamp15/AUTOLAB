#!/usr/bin/env python3
"""Make Forgejo hold what the lab's apps are built from.

    forgejo_bootstrap.py <settings.json>

Two organizations: `mirrors` (pull mirrors of the upstream projects, kept in
step on a schedule, so a project that is taken down or rewritten is still here)
and `apps` (our forks, ordinary repositories we change and build from).
Everything is declared in the settings file the role writes; the script
creates what is missing and never touches what exists, so a fork's history is
never reset. The last line is CHANGED or UNCHANGED, for Ansible.

Settings: {"url": "http://host:port", "token_file": "...",
           "orgs": {"mirrors": "...", "apps": "..."},
           "mirrors": [{"name": "...", "url": "https://github.com/..."}],
           "forks": ["name", ...], "mirror_interval": "8h0m0s"}
"""
import json
import sys
import urllib.error
import urllib.request


class Api:
    def __init__(self, base, token):
        self.base, self.token = base.rstrip("/") + "/api/v1", token

    def call(self, method, path, body=None, timeout=900):
        request = urllib.request.Request(
            self.base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"token {self.token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            payload = error.read().decode(errors="replace")
            try:
                return error.code, json.loads(payload)
            except ValueError:
                return error.code, {"message": payload[:200]}


def main():
    cfg = json.load(open(sys.argv[1]))
    api = Api(cfg["url"], open(cfg["token_file"]).read().strip())
    changed = False

    def ensure(path, create_path, body, what):
        nonlocal changed
        status, _ = api.call("GET", path)
        if status == 200:
            return
        if status != 404:
            sys.exit(f"forgejo: looking up {what} gave HTTP {status}")
        status, result = api.call("POST", create_path, body)
        if status not in (200, 201, 202):
            sys.exit(f"forgejo: creating {what} failed: HTTP {status} {result.get('message')}")
        print(f"forgejo: created {what}")
        changed = True

    for org, description in cfg["orgs"].items():
        ensure(f"/orgs/{org}", "/orgs", {"username": org, "visibility": "public", "description": description},
               f"organization {org}")
    for mirror in cfg["mirrors"]:
        ensure(f"/repos/mirrors/{mirror['name']}", "/repos/migrate", {
            "clone_addr": mirror["url"], "repo_name": mirror["name"], "repo_owner": "mirrors", "mirror": True,
            "mirror_interval": cfg["mirror_interval"], "service": "github", "private": False, "issues": False,
            "releases": False, "wiki": False, "pull_requests": False, "labels": False, "milestones": False},
            f"mirror mirrors/{mirror['name']}")
    for name in cfg["forks"]:
        ensure(f"/repos/apps/{name}", f"/repos/mirrors/{name}/forks", {"organization": "apps", "name": name},
               f"fork apps/{name}")
    print("CHANGED" if changed else "UNCHANGED")


if __name__ == "__main__":
    main()
