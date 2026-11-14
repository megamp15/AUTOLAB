# Registers Pocket ID as AdventureLog's OpenID Connect login.
#
# AdventureLog keeps its login providers in its database and has no
# environment variables for them: the documented way is a form in the Django
# admin. This is that form as code. It runs inside the app container through
# `manage.py shell`, reads its settings from the environment of that one exec
# (never from the container's own), and says CHANGED or UNCHANGED as its last
# line so Ansible can tell a converged host from one that just gained a login.
#
# The provider ID is the last part of the callback URL registered in Pocket ID:
#   <SITE_URL>/accounts/oidc/<provider_id>/login/callback/
import os

from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site

provider_id = os.environ["AL_OIDC_PROVIDER_ID"]
want = {
    "name": os.environ["AL_OIDC_NAME"],
    "client_id": os.environ["AL_OIDC_CLIENT_ID"],
    "secret": os.environ["AL_OIDC_CLIENT_SECRET"],
    "key": "",
    "settings": {"server_url": os.environ["AL_OIDC_ISSUER"]},
}

site = Site.objects.get_current()
# The site's name and domain show up in emails and the admin; the placeholder
# it ships with ("example.com") is a thing nobody means to leave.
host = os.environ["AL_SITE_HOST"]
changed = False
if site.domain != host or site.name != host:
    site.domain = site.name = host
    site.save()
    changed = True

app, created = SocialApp.objects.get_or_create(
    provider="openid_connect", provider_id=provider_id, defaults=want
)
changed = changed or created
for field, value in want.items():
    if getattr(app, field) != value:
        setattr(app, field, value)
        changed = True
if changed:
    app.save()
if not app.sites.filter(pk=site.pk).exists():
    app.sites.add(site)
    changed = True

print("CHANGED" if changed else "UNCHANGED")
