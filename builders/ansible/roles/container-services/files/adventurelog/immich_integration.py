"""Configure the administrator's own Immich connection, without logging its key."""
import os

import requests
from django.contrib.auth import get_user_model
from integrations.models import ImmichIntegration

url = os.environ['AL_IMMICH_URL'].rstrip('/')
key = os.environ['AL_IMMICH_KEY']
email = os.environ['AL_ADMIN_EMAIL'].strip()
response = requests.get(f'{url}/users/me', headers={'x-api-key': key}, timeout=15)
response.raise_for_status()
if response.json().get('email', '').casefold() != email.casefold():
    raise RuntimeError('Immich key belongs to a different email address')
user = get_user_model().objects.get(email__iexact=email)
existing = list(ImmichIntegration.objects.filter(user=user))
if len(existing) > 1:
    raise RuntimeError('Multiple Immich integrations exist for this account')
if existing and existing[0].server_url.rstrip('/') != url:
    raise RuntimeError('An Immich integration for a different server already exists')
if existing:
    integration = existing[0]
    changed = integration.api_key != key or integration.server_url != url
    if changed:
        integration.api_key = key
        integration.server_url = url
        integration.save(update_fields=['api_key', 'server_url'])
else:
    ImmichIntegration.objects.create(user=user, server_url=url, api_key=key)
    changed = True
print('CHANGED' if changed else 'UNCHANGED')
