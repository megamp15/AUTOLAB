#!/usr/bin/env python3
"""Provision restricted Pocket ID clients with recoverable root-only state."""
import fcntl
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid

STATE = Path('/etc/autolab/managed-pocketid-clients.json')
POLICY = Path('/etc/autolab/managed-pocketid-policy.json')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Api:
    def __init__(self, issuer, token):
        self.base = issuer.rstrip('/') + '/api'
        self.token = token

    def request(self, method, path, data=None, allow_missing=False):
        request = urllib.request.Request(self.base + path, method=method,
            data=json.dumps(data).encode() if data is not None else None,
            headers={'X-API-KEY': self.token, 'Content-Type': 'application/json'})
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
                body = response.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as error:
            if error.code == 404 and allow_missing:
                return None
            raise RuntimeError(f'Pocket ID request failed: HTTP {error.code}') from None
        except urllib.error.URLError:
            raise RuntimeError('Pocket ID is unreachable') from None


def save_state(path, state):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.managed-pocketid-')
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(state, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def reconcile(api, policy, state, save):
    groups = api.request('GET', '/user-groups?search=admins&pagination%5Blimit%5D=100')['data']
    matching = [g for g in groups if g['name'] == policy['group']]
    if len(matching) != 1:
        raise RuntimeError('Expected exactly one admins group')
    group_id = matching[0]['id']
    changed = False
    for name, settings in policy['clients'].items():
        entry = state.get(name)
        if entry is None:
            query = urllib.parse.urlencode({'search': 'AUTOLAB ' + name, 'pagination[limit]': 100})
            existing = api.request('GET', '/oidc/clients?' + query)['data']
            if any(client.get('name') == 'AUTOLAB ' + name for client in existing):
                raise RuntimeError('A client with this managed name exists but its state is missing')
            entry = {'id': 'autolab-' + name + '-' + uuid.uuid4().hex, 'secret': secrets.token_urlsafe(48)}
            state[name] = entry
            save(state)  # Persist before creating anything, so retries never invent another identity.
            changed = True
        path = '/oidc/clients/' + urllib.parse.quote(entry['id'], safe='')
        current = api.request('GET', path, allow_missing=True)
        desired = {'id': entry['id'], 'name': 'AUTOLAB ' + name,
                   'callbackURLs': settings['callbacks'], 'launchURL': settings['launch'],
                   'isPublic': False, 'isGroupRestricted': True}
        if current is None:
            if entry.get('secret_id'):
                raise RuntimeError('A managed Pocket ID client was deleted; restore or reconcile manually')
            api.request('POST', '/oidc/clients', desired)
            current = api.request('GET', path)
            changed = True
        elif current.get('name') != desired['name']:
            raise RuntimeError('Managed client ID is owned by another client')
        # Restrict first; a missing group is denied until group assignment succeeds.
        update = dict(current)
        update.update(desired)
        if any(current.get(k) != desired[k] for k in ('name', 'callbackURLs', 'launchURL', 'isPublic', 'isGroupRestricted')):
            api.request('PUT', path, update)
            changed = True
        current = api.request('GET', path)
        if not current.get('isGroupRestricted'):
            raise RuntimeError('Pocket ID client is not group restricted')
        actual_groups = {group['id'] for group in current.get('allowedUserGroups', [])}
        if actual_groups != {group_id}:
            api.request('PUT', path + '/allowed-user-groups', {'userGroupIds': [group_id]})
            changed = True
        current = api.request('GET', path)
        if not current.get('isGroupRestricted') or {g['id'] for g in current.get('allowedUserGroups', [])} != {group_id}:
            raise RuntimeError('Pocket ID group restriction did not apply')
        remote_secrets = api.request('GET', path + '/secrets') or []
        if entry.get('secret_id'):
            if not any(item['id'] == entry['secret_id'] and item.get('isActive', True) and not item.get('expiresAt') for item in remote_secrets):
                raise RuntimeError('Managed Pocket ID secret is missing or inactive')
        else:
            if remote_secrets:
                raise RuntimeError('Unrecorded Pocket ID secret exists; reconcile manually')
            created = api.request('POST', path + '/secrets', {'secret': entry['secret']})
            entry['secret_id'] = created['id']
            save(state)
            changed = True
    return changed


def main():
    token = os.environ['AUTOLAB_POCKETID_API_KEY']
    policy = json.loads(POLICY.read_text())
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with open('/run/autolab-pocketid-clients.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if STATE.exists():
            if STATE.is_symlink() or STATE.stat().st_uid != 0 or STATE.stat().st_mode & 0o077:
                raise RuntimeError('Managed Pocket ID state must be root-only')
            state = json.loads(STATE.read_text())
        else:
            state = {}
        changed = reconcile(Api(policy['issuer'], token), policy, state, lambda data: save_state(STATE, data))
    print('CHANGED' if changed else 'UNCHANGED')


if __name__ == '__main__':
    try:
        main()
    except (KeyError, ValueError, RuntimeError, OSError) as error:
        print(f'Pocket ID provisioning failed: {error}', file=sys.stderr)
        sys.exit(1)
