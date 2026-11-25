#!/usr/bin/env python3
"""Bounded, read-only homepage queries. Internal compose listener; nginx fronts it."""
import concurrent.futures
import http.server
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import urllib.parse
import urllib.request

from homepage_metrics import collect_telemetry, storage_pools, filesystems, backup_status


def get_json(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.load(response)


def number(value):
    n = float(value)
    return n if math.isfinite(n) else None


class HomepageData:
    def __init__(self, status, prometheus, loki):
        self.status = status
        self.prometheus = prometheus.rstrip('/')
        self.loki = loki.rstrip('/')
        self.lock = threading.Lock()
        self.cached = None
        self.cached_at = 0
        self.pipelines = {}

    def prom(self, query):
        result = get_json(self.prometheus + '/api/v1/query?' + urllib.parse.urlencode({'query': query}))
        if result.get('status') != 'success':
            raise ValueError('Metrics query failed')
        return result['data']['result']

    def snapshot(self):
        with self.lock:
            if self.cached is not None and time.monotonic() - self.cached_at < 15:
                return self.cached
            status = get_json(self.status) if self.status.startswith(('http://', 'https://')) else json.loads(Path(self.status).read_text())
            errors = status.setdefault('operations', {}).setdefault('errors', [])
            telemetry = status['operations'].setdefault('telemetry', {})
            for key, collect in ((None, collect_telemetry), ('pools', storage_pools), ('filesystems', filesystems), ('backups', backup_status)):
                try:
                    result = collect(self.prom)
                    if key:
                        telemetry[key] = result
                    else:
                        telemetry.update(result)
                except Exception:
                    if key:
                        telemetry[key] = {} if key == 'backups' else []
                    errors.append((key or 'telemetry') + ': source unavailable')
            status['metrics_generated'] = int(time.time())
            self.cached, self.cached_at = status, time.monotonic()
            return status

    def pipeline(self, host):
        """One host's containers (CPU, memory, limit, network) and its NFS traffic, for the
        Novaflix pipeline drawing. Fixed queries; the host is a plain name."""
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,40}', host):
            raise ValueError('Invalid host')
        with self.lock:
            kept = self.pipelines.get(host)
            if kept and time.monotonic() - kept[0] < 4:
                return kept[1]
        label = json.dumps(host)
        by = 'container_label_com_docker_compose_service'
        sel = '{instance=' + label + ',' + by + '!=""}'
        queries = {
            'cpu': 'sum by (' + by + ') (rate(container_cpu_usage_seconds_total' + sel + '[1m]))',
            'memory': 'sum by (' + by + ') (container_memory_working_set_bytes' + sel + ')',
            'limit': 'max by (' + by + ') (container_spec_memory_limit_bytes' + sel + ' > 0)',
            'received': 'sum by (' + by + ') (rate(container_network_receive_bytes_total' + sel + '[1m]))',
            'sent': 'sum by (' + by + ') (rate(container_network_transmit_bytes_total' + sel + '[1m]))',
            'nfs_read': 'sum(rate(node_mountstats_nfs_total_read_bytes_total{instance=' + label + '}[1m]))',
            'nfs_write': 'sum(rate(node_mountstats_nfs_total_write_bytes_total{instance=' + label + '}[1m]))',
        }
        def run(item):
            key, query = item
            try:
                return key, self.prom(query)
            except Exception:
                return key, None
        with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
            answers = dict(executor.map(run, queries.items()))
        services = {}
        for key in ('cpu', 'memory', 'limit', 'received', 'sent'):
            for row in answers[key] or []:
                name = row['metric'].get(by)
                if name:
                    services.setdefault(name, {})[key] = number(row['value'][1])
        def single(key):
            rows = answers[key]
            return number(rows[0]['value'][1]) if rows else None
        result = {'host': host, 'generated': int(time.time()), 'services': services,
                  'nfs': {'read': single('nfs_read'), 'write': single('nfs_write')}}
        with self.lock:
            self.pipelines[host] = (time.monotonic(), result)
        return result

    def detail(self, node, vm='', container='', period='1h'):
        if period not in ('1h', '6h', '24h'):
            raise ValueError('Unsupported time range')
        status = self.snapshot()
        hosts = status['operations'].get('nodes', [])
        selected = next((n for n in hosts if n['name'] == node), None)
        if not selected:
            raise ValueError('Unknown Proxmox node')
        guest = next((g for g in selected.get('guests', []) if g['name'] == vm), None) if vm else None
        if vm and not guest:
            raise ValueError('Unknown VM on this node')
        host = vm or node
        tel = status['operations'].get('telemetry', {})
        containers = [c for c in tel.get('containers', []) if c['host'] == host]
        tenant = guest and any(t.startswith('tenant-') for t in str(guest.get('tags', '')).split(';'))
        if container and (tenant or not any(c['name'] == container for c in containers)):
            raise ValueError('Unknown container on this VM')
        label = json.dumps(host)
        selector = '{instance=' + label + '}'
        queries = {
            'CPU': ('100 * (1 - avg(rate(node_cpu_seconds_total{instance=' + label + ',mode="idle"}[5m])))', '%'),
            'Memory': ('100 * (1 - node_memory_MemAvailable_bytes' + selector + ' / node_memory_MemTotal_bytes' + selector + ')', '%'),
            'Root filesystem': ('100 * (1 - node_filesystem_free_bytes{instance=' + label + ',mountpoint="/",fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{instance=' + label + ',mountpoint="/",fstype!~"tmpfs|overlay"})', '%'),
            'Network received': ('sum(rate(node_network_receive_bytes_total{instance=' + label + ',device!~"lo|veth.*|docker.*|br-.*"}[5m]))', 'B/s'),
            'Network sent': ('sum(rate(node_network_transmit_bytes_total{instance=' + label + ',device!~"lo|veth.*|docker.*|br-.*"}[5m]))', 'B/s'),
        }
        if container:
            sel = '{instance=' + label + ',name=' + json.dumps(container) + '}'
            queries = {
                'CPU': ('sum(rate(container_cpu_usage_seconds_total' + sel + '[5m]))', 'cores'),
                'Working memory': ('sum(container_memory_working_set_bytes' + sel + ')', 'B'),
                'Network received': ('sum(rate(container_network_receive_bytes_total' + sel + '[5m]))', 'B/s'),
                'Network sent': ('sum(rate(container_network_transmit_bytes_total' + sel + '[5m]))', 'B/s'),
            }
        seconds = {'1h': 3600, '6h': 21600, '24h': 86400}[period]
        end = int(time.time())
        def series(item):
            title, (query, unit) = item
            params = urllib.parse.urlencode({'query': query, 'start': end - seconds, 'end': end, 'step': max(30, seconds // 180)})
            try:
                result = get_json(self.prometheus + '/api/v1/query_range?' + params)['data']['result']
                return {'title': title, 'unit': unit, 'values': [[float(t), number(v)] for t, v in result[0]['values']] if result else []}
            except Exception:
                return {'title': title, 'unit': unit, 'values': [], 'error': 'Source unavailable'}
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            charts = list(executor.map(series, queries.items()))
        # Tenant application logs are outside the provider's baseline view.
        log_query = '{host=' + label + ',job="journald"}'
        if container:
            log_query = '{host=' + label + ',job="docker",container=' + json.dumps(container) + '}'
        elif vm and not tenant:
            log_query = '{host=' + label + '}'
        log_error, logs = None, []
        try:
            params = urllib.parse.urlencode({'query': log_query, 'start': (end - seconds) * 1000000000, 'end': end * 1000000000, 'limit': 40, 'direction': 'backward'})
            result = get_json(self.loki + '/loki/api/v1/query_range?' + params)['data']['result']
            for stream in result:
                for stamp, line in stream['values']:
                    logs.append({'time': int(stamp) / 1e9, 'text': line[:2000], 'container': stream['stream'].get('container', '')})
            logs.sort(key=lambda item: item['time'], reverse=True)
        except Exception:
            log_error = 'Log source unavailable'
        return {'generated': end, 'range': period, 'charts': charts, 'logs': logs[:40], 'log_error': log_error,
                'pools': [p for p in tel.get('pools', []) if p['node'] == node] if not vm else [],
                'filesystems': [f for f in tel.get('filesystems', []) if f['host'] == host],
                'containers': [] if tenant else containers, 'tenant': bool(tenant),
                'backups': [b for b in tel.get('backups', {}).get('guests', []) if b['name'] in ([vm] if vm else [g['name'] for g in selected.get('guests', [])])],
                'backup_collected': tel.get('backups', {}).get('collected')}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path)
        params = urllib.parse.parse_qs(path.query)
        # The pipeline copy of this service answers that route and nothing else: it shares a
        # network with Novaflix, which must not reach the status page or the logs.
        routes = self.server.routes
        if routes is not None and path.path not in routes:
            self.send_error(404)
            return
        try:
            if path.path == '/api/pipeline':
                if set(params) - {'host'} or any(len(v) != 1 for v in params.values()):
                    raise ValueError('Invalid pipeline parameters')
                result = self.server.data.pipeline(params.get('host', [''])[0])
            elif path.path == '/api/status':
                result = self.server.data.snapshot()
            elif path.path == '/api/detail':
                if set(params) - {'node', 'vm', 'container', 'range'} or any(len(v) != 1 or len(v[0]) > 200 for v in params.values()):
                    raise ValueError('Invalid detail parameters')
                result = self.server.data.detail(params.get('node', [''])[0], params.get('vm', [''])[0], params.get('container', [''])[0], params.get('range', ['1h'])[0])
            else:
                self.send_error(404)
                return
            self.reply(200, result)
        except ValueError as error:
            self.reply(400, {'error': str(error)})
        except Exception:
            self.reply(502, {'error': 'Monitoring source unavailable'})

    def reply(self, status, result):
        body = json.dumps(result, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    server = http.server.ThreadingHTTPServer(('0.0.0.0', 8081), Handler)
    # HOMEPAGE_ROUTES: when set, the only paths this copy answers (comma separated).
    routes = os.environ.get('HOMEPAGE_ROUTES')
    server.routes = {route.strip() for route in routes.split(',') if route.strip()} if routes else None
    server.data = HomepageData(os.environ.get('HOMEPAGE_STATUS', '/site/status.json'), os.environ.get('PROMETHEUS_URL', 'http://prometheus:9090'), os.environ.get('LOKI_URL', 'http://loki:3100'))
    server.serve_forever()
