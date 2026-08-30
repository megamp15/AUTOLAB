#!/usr/bin/env python3
"""Render inventory from `builder_machines`; use `gitops` after bootstrap or `autolab` as break-glass."""

import argparse
import json
import sys
from pathlib import Path


def _validate(machines: object) -> dict[str, dict]:
    if not isinstance(machines, dict):
        raise ValueError("top-level value must be an object map")

    for key, machine in machines.items():
        if not isinstance(machine, dict):
            raise ValueError(f"machine {key!r} must be an object")
        for field in ("name", "ansible_host", "bootstrap_user"):
            if not isinstance(machine.get(field), str) or not machine[field]:
                raise ValueError(f"machine {key!r}.{field} must be a non-empty string")
        builder = machine.get("builder")
        if not isinstance(builder, dict):
            raise ValueError(f"machine {key!r}.builder must be an object")
        if not isinstance(builder.get("enabled"), bool):
            raise ValueError(f"machine {key!r}.builder.enabled must be a boolean")
        if "firewall_rules" in builder:
            rules = builder["firewall_rules"]
            if not isinstance(rules, list):
                raise ValueError(f"machine {key!r}.builder.firewall_rules must be a list")
            for index, rule in enumerate(rules):
                if not isinstance(rule, dict):
                    raise ValueError(f"machine {key!r}.builder.firewall_rules[{index}] must be an object")
                if not isinstance(rule.get("port"), int) or isinstance(rule["port"], bool) or not 1 <= rule["port"] <= 65535:
                    raise ValueError(f"machine {key!r}.builder.firewall_rules[{index}].port must be 1..65535")
                if rule.get("protocol") not in ("tcp", "udp"):
                    raise ValueError(f"machine {key!r}.builder.firewall_rules[{index}].protocol must be tcp or udp")
                if not isinstance(rule.get("source"), str):
                    raise ValueError(f"machine {key!r}.builder.firewall_rules[{index}].source must be a string")
        for field in ("docker_enabled",):
            if field in builder and not isinstance(builder[field], bool):
                raise ValueError(f"machine {key!r}.builder.{field} must be a boolean")

    if not any(machine["builder"]["enabled"] for machine in machines.values()):
        raise ValueError("no enabled builder hosts")
    return machines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON from tofu output -json builder_machines")
    parser.add_argument("--output", type=Path, help="write inventory here instead of stdout")
    parser.add_argument("--user", default="gitops", help="Ansible SSH user after bootstrap")
    args = parser.parse_args()
    try:
        machines = _validate(json.loads(args.input.read_text()))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    hosts = {
        machine["name"]: {
            "ansible_host": machine["ansible_host"],
            "ansible_user": args.user,
            "autolab_bootstrap_user": machine["bootstrap_user"],
            "autolab_builder": machine["builder"],
        }
        for machine in machines.values()
        if machine["builder"]["enabled"]
    }
    rendered = json.dumps({"all": {"children": {"linux_servers": {"hosts": hosts}}}}, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
