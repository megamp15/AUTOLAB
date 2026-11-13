"""Shared read-only metrics for the homepage collector and detail API."""
import math

def collect_telemetry(prom):
    # Live numbers for the architecture diagram, from what Alloy and cAdvisor
    # already send: per host (node_exporter) and per container. One query per
    # figure; a host or container missing from one simply lacks that figure.
    hosts, containers = {}, {}
    for key, query in (
        ("cores", 'count by (instance) (node_cpu_seconds_total{mode="idle"})'),
        ("cpu", '1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))'),
        ("mem_total", 'node_memory_MemTotal_bytes'),
        ("mem_used", 'node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes'),
        ("disk", '1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}'),
        ("uptime", 'node_time_seconds - node_boot_time_seconds'),
        ("load", 'node_load1'),
    ):
        for r in prom(query):
            instance = r["metric"].get("instance")
            if instance:
                value = float(r["value"][1])
                if math.isfinite(value):
                    hosts.setdefault(instance, {"name": instance})[key] = value
    for key, query in (
        ("mem", 'sum by (instance, name) (container_memory_working_set_bytes{name!=""})'),
        ("cpu", 'sum by (instance, name) (rate(container_cpu_usage_seconds_total{name!=""}[5m]))'),
    ):
        for r in prom(query):
            m = r["metric"]
            if m.get("instance") and m.get("name"):
                value = float(r["value"][1])
                if math.isfinite(value):
                    containers.setdefault((m["instance"], m["name"]), {"host": m["instance"], "name": m["name"]})[key] = value
    return {"hosts": sorted(hosts.values(), key=lambda h: h["name"]),
            "containers": sorted(containers.values(), key=lambda c: (c["host"], c["name"]))}

def storage_pools(prom):
    """Keep node/storage identity and physical usage; never sum shared stores."""
    pools = {}
    for r in prom('last_over_time(pve_storage_info[1h])'):
        m = r["metric"]
        pools[(m["instance"], m["id"])] = {
            "id": m["id"], "instance": m["instance"], "node": m.get("node"),
            "name": m.get("storage"), "type": m.get("plugintype"),
            "content": m.get("content", ""), "used": None, "total": None,
            "active": False, "shared": False,
        }
    for metric, field in (("pve_disk_size_bytes", "total"), ("pve_disk_usage_bytes", "used"),
                          ("pve_up", "active"), ("pve_storage_shared", "shared")):
        for r in prom(metric + '{id=~"storage/.*"}'):
            m = r["metric"]
            p = pools.get((m["instance"], m["id"]))
            value = float(r["value"][1])
            if p is not None and math.isfinite(value):
                p[field] = bool(value) if field in ("active", "shared") else value
    healthy = {r["metric"]["instance"] for r in prom('up{job="pve"}') if float(r["value"][1]) == 1}
    for p in pools.values():
        p["active"] = p["active"] and p["instance"] in healthy
        if not p["active"] or not p["total"] or p["used"] is None:
            p["used"], p["total"] = None, None
        p["free"] = max(0, p["total"] - p["used"]) if p["total"] else None
    return sorted(pools.values(), key=lambda p: (p["node"] or "", p["name"] or ""))


def filesystems(prom):
    mounts = {}
    selector = '{fstype!~"tmpfs|devtmpfs|overlay|squashfs|fuse.*|nsfs"}'
    for metric, field in (("node_filesystem_size_bytes", "total"), ("node_filesystem_avail_bytes", "available"),
                          ("node_filesystem_free_bytes", "free")):
        for r in prom(metric + selector):
            m = r["metric"]
            k = (m.get("instance"), m.get("mountpoint"), m.get("device"))
            value = float(r["value"][1])
            if math.isfinite(value):
                mounts.setdefault(k, {"host": k[0], "mount": k[1], "device": k[2], "type": m.get("fstype")})[field] = value
    for mount in mounts.values():
        if "total" in mount and "free" in mount:
            mount["used"] = mount["total"] - mount["free"]
    return list(mounts.values())


def backup_status(prom):
    guests = {}
    for metric, field in (("autolab_backup_last_seconds", "last"), ("autolab_backup_excluded", "excluded")):
        for r in prom(metric):
            m = r["metric"]
            if m.get("name") and m.get("vmid"):
                record = guests.setdefault((m["name"], m["vmid"]), {"name": m["name"], "vmid": m["vmid"]})
                record[field] = float(r["value"][1])
    clocks = [float(r["value"][1]) for r in prom('autolab_backup_collector_timestamp_seconds')]
    return {"guests": list(guests.values()), "collected": max(clocks) if clocks else None}
