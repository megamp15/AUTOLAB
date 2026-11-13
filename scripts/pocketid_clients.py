"""Adopt existing Pocket ID clients and reconcile declared browser URLs.

Prepare adds callbacks without breaking the running configuration. Apply after
service deployment removes obsolete callbacks. Client credentials, groups,
consent settings and other undeclared fields stay as returned by Pocket ID.
"""

import argparse
import copy
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request


POLICY = Path(__file__).resolve().parents[1] / "builders/ansible/pocketid-clients.json"


def desired_clients(variables, policy):
    labels = variables["autolab_ingress_hostnames"]
    names = dict(labels, zone=variables["autolab_ingress_zone"],
                 internal=variables["autolab_ingress_internal_label"])
    if not names["zone"] or not names["internal"]:
        raise ValueError("Private dashboard zone and internal label are required")
    clients = {}
    for name, fields in policy.items():
        client_id = variables.get(fields["id_variable"], "")
        if not client_id:
            continue
        settings = {}
        for key, value in fields.items():
            if key != "id_variable":
                settings[key] = ([url.format(**names) for url in value]
                                 if isinstance(value, list) else value.format(**names))
        clients[name] = (client_id, settings)
    return clients


def reconcile(current, desired, prepare=False):
    result = copy.deepcopy(current)
    for key, value in desired.items():
        if prepare:
            if key not in ("callbackURLs", "logoutCallbackURLs"):
                continue
            value = list(dict.fromkeys((current.get(key) or []) + value))
        result[key] = value
    return result


class Api:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.token = token

    def request(self, method, client_id, body=None):
        url = self.base_url + "/api/oidc/clients/" + urllib.parse.quote(client_id, safe="")
        request = urllib.request.Request(
            url, method=method, data=json.dumps(body).encode() if body is not None else None,
            headers={"X-API-KEY": self.token, "Content-Type": "application/json",
                     "User-Agent": "autolab-status/1.0"},
        )
        # Do not send the administration credential to a redirect destination.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            # Response bodies can contain credentials or full client settings.
            raise RuntimeError(f"Pocket ID {method} failed with HTTP {error.code}") from None
        except urllib.error.URLError:
            raise RuntimeError("Pocket ID is unreachable") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variables", required=True, type=Path)
    parser.add_argument("--client", choices=("traefik", "grafana"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    variables = json.loads(args.variables.read_text())
    clients = desired_clients(variables, json.loads(POLICY.read_text()))
    if args.client:
        clients = {name: value for name, value in clients.items() if name == args.client}
    if not clients:
        print("No configured Pocket ID clients to manage")
        return
    token = os.environ.get("POCKETID_API_KEY", "").strip()
    if not token:
        raise ValueError("POCKETID_API_KEY is required to manage configured clients")
    labels = variables["autolab_ingress_hostnames"]
    base_url = "https://" + labels["auth"] + "." + variables["autolab_ingress_zone"]
    api = Api(base_url, token)
    # Read every client before changing any. Missing clients are an error;
    # this migration never creates replacements or rotates their secrets.
    existing = {name: api.request("GET", client_id) for name, (client_id, _) in clients.items()}
    for name, (client_id, desired) in clients.items():
        current = existing[name]
        payload = reconcile(current, desired, prepare=args.prepare)
        if payload == current:
            print(f"{name}: unchanged")
            continue
        if not (args.apply or args.prepare):
            print(f"{name}: URL configuration would change")
            continue
        api.request("PUT", client_id, payload)
        actual = api.request("GET", client_id)
        if any(actual.get(key) != payload[key] for key in desired if key in payload
               and (not args.prepare or key in ("callbackURLs", "logoutCallbackURLs"))):
            raise RuntimeError(f"{name}: URL configuration verification failed")
        if actual.get("allowedUserGroups") != current.get("allowedUserGroups"):
            raise RuntimeError(f"{name}: group restrictions changed unexpectedly")
        print(f"{name}: {'private callbacks prepared' if args.prepare else 'private URLs applied'}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
