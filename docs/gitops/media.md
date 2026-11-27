---
tags: [gitops, media, jellyfin, aurora, nas, edge]
status: draft
audience: operator
---

# Media

`aurora` is a VM on zima-pve (edge Stack, VMID 303, 4 vCPU, 6 GB, 150 GB on
the HDD). It runs Jellyfin, which plays the films and shows kept on the NAS, and the
apps that fetch them: Prowlarr, Sonarr, Radarr, Lidarr, Bazarr, SABnzbd,
qBittorrent behind Gluetun and Mullvad, and Recyclarr. Seerr is the page the
household uses to see what is trending and request it.

## The download apps

| app | name on the tailnet | does |
|---|---|---|
| Prowlarr | `prowlarr.lab.<zone>` | holds the indexers and hands them to Sonarr and Radarr |
| Sonarr | `sonarr.lab.<zone>` | finds series (shows, anime, dramas) and files them into their library folder |
| Radarr | `radarr.lab.<zone>` | the same for films |
| Lidarr | `lidarr.lab.<zone>` | the same for music, into the Music library |
| Recyclarr | no page | copies TRaSH Guides' quality profiles into Sonarr and Radarr once a day |
| Bazarr | `bazarr.lab.<zone>` | fetches subtitles for what the two have filed |
| SABnzbd | `sabnzbd.lab.<zone>` | downloads from Usenet |
| qBittorrent | `qbittorrent.lab.<zone>` | downloads torrents, only through the Mullvad tunnel |

All six are tailnet-only, behind the passkey (`login: plugin`), and none is
published on the home network. Sonarr, Radarr and Prowlarr run with
`AUTH__METHOD=External`, so the passkey is the one login. qBittorrent keeps
its own login as well.

qBittorrent shares Gluetun's network (`network_mode: service:gluetun`).
Gluetun holds a WireGuard tunnel to Mullvad and a firewall that lets nothing
out except through it, so a dropped tunnel leaves qBittorrent with no network
rather than on the home connection. The key and address are the
`MULLVAD_WIREGUARD_*` secrets; the servers are
`autolab_services_mullvad_cities`. Usenet needs no tunnel: the connection to
the provider is TLS.

Every app sees the share whole at `/data`:

```text
/data/media/<library folder>   what Jellyfin plays (read-only to Jellyfin)
/data/usenet/incomplete        SABnzbd's downloads in progress
/data/usenet/complete          SABnzbd's finished downloads
/data/torrents                 qBittorrent's downloads
```

One tree on one share means an import is a rename (Usenet) or a hardlink
(torrents, which keep seeding), never a copy. SABnzbd downloads and unpacks
on the share too (`/data/usenet/incomplete`, direct unpack on, a 1 GB article
cache), so a download never touches zima-pve's one hard drive, which every VM
on the node shares. aurora mounts the share over the home network, not the
tailnet: see [NAS storage](nas-storage.md#a-mount-over-the-home-network).

## Who reaches Jellyfin, and how

| from | address | what is in front |
|---|---|---|
| a device at home (the projector, a TV) | `http://<aurora's home address>:8096` | Jellyfin's sign-in |
| a device on the tailnet | `https://jellyfin.lab.<zone>` | Jellyfin's sign-in |
| the internet (friends) | `https://jellyfin.<zone>` | Jellyfin's sign-in, behind the public door below |

The home address exists because the projector and the TVs are not on the
tailnet. Docker publishes 8096 and UDP 7359 on the machine's home address,
and aurora's `firewall_rules` open both to the home network only. The
docker-host role turns those rules into `DOCKER-USER` exceptions, because
Docker's own rules would otherwise send a published port past ufw. Any other
published port is still dropped on the home network. UDP 7359 lets a Jellyfin
app at home find the server without being given an address.

There is no passkey in front of either name. Jellyfin's apps on a phone or a
TV cannot answer a passkey page.

## Seerr: browse and request

Seerr shows what is trending, popular and coming soon, and sends a request to
Sonarr or Radarr. People sign in with their Jellyfin accounts, so there is no
second password. Novaflix's Requests screen stays the admin view (the queue, why
a download failed, deleting files); Seerr is the simple one for everyone else.

| from | address | what is in front |
|---|---|---|
| a device at home (a TV's browser, a phone) | `http://<aurora's home address>:5055` | Seerr's sign-in (Jellyfin accounts) |
| a device on the tailnet | `https://seerr.lab.<zone>` | the same |
| the internet | nothing | no public name |

5055 is open to the home network the same way 8096 is: published on the home
address and named in aurora's `firewall_rules`. Its settings, users and
requests are a SQLite database in `/opt/autolab/services/seerr`.

### Seerr's first run

Its settings are made in its own setup page, not in code:

1. Open it, choose Jellyfin, and sign in with the Jellyfin admin account.
   The Jellyfin address is `http://jellyfin:8096` (the same Compose network);
   the external address is `http://<aurora's home address>:8096`.
2. Pick the libraries to sync (all of them).
3. Add Radarr (`http://radarr:7878`) and Sonarr (`http://sonarr:8989`) with
   their API keys, the default quality profile and root folder, and mark each
   the default server.
   The default root folders are `/data/media/movies` and `/data/media/tv`:
   Seerr files every request there, and Novaflix moves each new one to the
   library its language says (Desi, K-dramas, anime) within five minutes.
4. Users, Import Jellyfin Users: each person signs in with their own account.
   Give them Request and Auto-Approve, or leave approval to an admin.

### On the TVs

| device | app |
|---|---|
| Google TV (the Valerion projector, the Sony) | Moonfin from the Play Store: plays from Jellyfin and has Seerr's browse and request inside, through the Moonfin plugin on Jellyfin |
| LG (webOS) | the Jellyfin app from LG's store to watch; Seerr in a phone's browser to request. Moonfin for webOS has to be sideloaded in developer mode |
## Friends, from the internet

`jellyfin.<zone>` reaches Jellyfin, and `seerr.<zone>` Seerr, from the internet
through the home router. No tunnel and no Cloudflare proxy: video goes straight
to the home connection.

```
friend ─▶ home router :443 ─▶ aurora 192.168.50.54:443 ─▶ jellyfin-public (Traefik) ─▶ jellyfin:8096
            port forward        US addresses only           these two names only        └▶ seerr:5055
```

| layer | what it does | where |
|---|---|---|
| dynamic DNS | `jellyfin-ddns` checks the home connection's address every 5 minutes and rewrites the record when the ISP changes it. DNS only (grey cloud) | `services.d/jellyfin-public.yml.j2` |
| certificate | Let's Encrypt through Cloudflare's DNS; Traefik renews it about 30 days before it expires, with no cron job | `jellyfin-public/traefik.yml.j2` |
| country | aurora's `firewall_rules` open 443 with `countries = ["US"]`; DOCKER-USER passes it only from the US address set, which `autolab-geoip-refresh.timer` fetches weekly from ipdeny.com. A failed fetch keeps the last list; no list at all lets nobody in | docker-host role |
| two names | the door answers only `jellyfin.<zone>` and `seerr.<zone>` (SNI strict: a scanner dialling the address gets no certificate), never `/Startup`, nor Seerr's own accounts (`/api/v1/auth/local`) or `/setup`, with a rate limit per address | `jellyfin-public/dynamic.yml.j2` |
| sign-in guessing | fail2ban bans an address for a day after 5 refused sign-ins in 10 minutes, Jellyfin's or Seerr's, on every port | jail `jellyfin-public` |
| reach | the door's network holds only it, Jellyfin and Seerr; the media is read-only to Jellyfin | the compose file |
| administrators | can sign in from home and the tailnet only (Jellyfin's per-user remote access), so a guessed admin password opens nothing from outside. The exception is whoever `autolab_services_jellyfin_remote_admins` names (the owner, so Moonfin's Seerr works away from home): the run leaves their remote access alone, and it is switched on once in Jellyfin. Seerr checks passwords from inside, so an administrator can still sign in to Seerr from outside: fail2ban and the password are what stand there | the services run |
| bandwidth | streams from outside are held to 10 Mbps (`autolab_services_jellyfin_remote_bitrate`) | the services run |

Jellyfin tells home from outside by the client's own address: the door's
address is its only trusted proxy, and the door drops any X-Forwarded-For a
client sends. Home is the home network, the tailnet and the containers' own
range.

### Turning it on

1. The services run with `jellyfin-public` in aurora's list (after `04` for the
   firewall rule, then `05` `docker` for the country set, then `05` `services`).
2. On the home router: forward TCP 443 to `192.168.50.54:443`. Nothing else.
3. A Jellyfin user per friend (Dashboard, Users): not an administrator, media
   deletion off, only the libraries they should see. Then Seerr, Users,
   Import Jellyfin Users: requests wait for approval, within the quota.

### Checking it

```sh
sudo fail2ban-client status jellyfin-public        # who is banned
sudo ipset list autolab-geo-us | head -8           # the US set and its size
sudo iptables -S DOCKER-USER                       # the 443 rule names the set
```

From a phone on mobile data: `https://jellyfin.<zone>` opens and a friend's
account signs in; the admin account is refused. With a VPN exit outside the US,
the page does not open.

## Video encoding: Quick Sync

A stream Jellyfin cannot send as it is (a format the app cannot play, or over
the 10 Mbps outside cap) is converted on the fly. On aurora's four N150 cores
that is about one 1080p stream. So aurora is handed zima-pve's Intel graphics
whole (`pci_mappings = ["zima-igpu"]`, a cluster PCI mapping in the edge
stack), the services run installs Intel's graphics firmware and passes
`/dev/dri/renderD128` into Jellyfin, and Jellyfin encodes with Quick Sync:
low-power H.264 and HEVC encoders (the only kind the N150 has), hardware
decoding of everything up to AV1, HDR tone-mapped to SDR on the chip.

Check it while something converts: Dashboard, Playback shows the stream as
transcoding, and `intel_gpu_top` on aurora shows the video engine busy. The
node itself runs headless and gives the device up while aurora runs.

## Where things are

| thing | where | why |
|---|---|---|
| films and shows | NAS, `/mnt/aurora/media-stack/media/<folder>`, one folder per library (share `/volume1/aurora`, NFS) | they outlive the VM; Jellyfin mounts them read-only |
| Jellyfin's settings, users and watch history | this VM's disk, `/opt/autolab/services/jellyfin/config` | a SQLite database, which does not belong on NFS |
| the download apps' settings | this VM's disk, `/opt/autolab/services/<app>` | SQLite databases again |
| the whole VM | PBS, nightly like every guest | the copy of the settings |

The films and shows are not backed up. They can be fetched again.

The share is named for the machine. Its one NFS rule names aurora's tailnet
address, so no other host can mount it. Anything else aurora keeps on the NAS
goes in a folder beside `media-stack`.

Jellyfin refuses to start while the share is not mounted. Its bind mount uses
`create_host_path: false`, and the boot unit waits for the mount, so an
unmounted share is an error and never an empty library on the local disk.

### When UGOS takes the share's permissions away

Saving a dialog for the `aurora` share in UGOS can reset the permissions on
everything in it (`nas-storage.md`, "Things that will mislead you"). On
2026-11-25 an NFS rule left every library file at mode `000`. The download
apps carried on, but Jellyfin runs as uid 1000 and could open nothing:
playback spun on "Loading stream", and its log said
`UnauthorizedAccessException ... is denied` and `FFmpeg exited with code 243`.

`autolab-media-access` on aurora puts it back, the same way
`autolab-pbs-access` does for PBS on ark:

```
every 15 min ──► as uid 1000, try every folder and file under media-stack/
                    │
                    ├─ all readable ──► change nothing (about 0.1 s)
                    │
                    └─ something blocked ──► as root: owner 1000:1000,
                                             folders 0775, files 0664
                                             └─► try again, report REPAIRED
```

Access is tried, not read off `ls`: the modes this NAS reports are made up
from its own permissions and can look right while access is denied.
`media-stack` itself stays root's. `autolab_media_readable` and
`autolab_media_access_repairs_total` go to Prometheus, and the
"Jellyfin cannot read the media share" alert fires when a repair did not
work. The services playbook runs the same check; `--check` reports without
changing anything:

```bash
sudo autolab-media-access --check
```

## First run

Jellyfin starts with no users. Open it on the tailnet name, make the
administrator account in its setup pages, and skip adding libraries.

Then make an API key under Dashboard, API Keys, named `autolab`, and store it
as the `JELLYFIN_API_KEY` secret. The next services run creates the libraries.

### The download apps

Their wiring is not code yet; set it in each app's UI:

1. SABnzbd: its first-run wizard asks for the Usenet server. Categories
   `tv` and `movies`, completed folder `/data/usenet/complete`. The
   services run sets the temporary folder (`/data/usenet/incomplete`),
   direct unpack and the cache.
2. qBittorrent: the first password is in its log
   (`docker compose logs qbittorrent` in `/opt/autolab/services`). Change it, and set the default save
   path to `/data/torrents`.
3. Prowlarr: add the indexers, then Sonarr and Radarr under Apps
   (`http://sonarr:8989`, `http://radarr:7878`, with each app's API key).
4. Sonarr and Radarr: download clients `sabnzbd:8080` and `gluetun:8080`
   (qBittorrent is reached through Gluetun's name), and a root folder per
   library: `/data/media/tv`, `/data/media/anime`, `/data/media/kdrama` and
   so on for Sonarr, the movie folders for Radarr. Anime series use the
   Anime series type.
5. Bazarr: connect Sonarr and Radarr the same way.

### Recyclarr

The settings are `files/recyclarr/recyclarr.yml` in the container-services
role. Shows get TRaSH's WEB-1080p profile and films HD Bluray + WEB, each with
"Language: Not Original" (so a Korean drama comes in Korean, never dubbed) and
the Asian streaming services boost. Anime gets TRaSH's anime profile on both.
Pick the profile when adding a title: the anime one for anime, the other for
everything else. The services run writes `secrets.yml` beside the settings
from Sonarr's and Radarr's own API keys.

It also sets their naming to TRaSH's Jellyfin presets: a show's folder ends in
`[tvdbid-…]` and a film's in `[tmdbid-…]`, so Jellyfin matches the exact title
instead of guessing from the name (it once matched a new K-drama to the wrong
show), and files are renamed to `Show (Year) - S01E01 - Title [quality]`.

Jellyfin cannot watch the folders itself: change notifications do not cross
NFS. Novaflix asks it to scan within five minutes of a new film or episode
landing. Sonarr and Radarr cannot: Jellyfin sits on the public door's network
only, away from theirs, so a break-in at Jellyfin reaches no download app.
Music waits for Jellyfin's own scheduled scan. Real-time monitoring stays on
in every library (the services run turns it on; a library made with it off
ignored a new show's folder).

Recyclarr syncs once a day. To sync now, or to see what it would change:

```sh
cd /opt/autolab/services
sudo docker compose exec recyclarr recyclarr sync --preview   # what would change
sudo docker compose exec recyclarr recyclarr sync
```

### Stopping one

A stopped container uses no memory. Take an app out of aurora's `services`
list to stop it for good; its settings stay in `/opt/autolab/services/<app>`
and come back when the name does. Stopping it in Dockhand lasts until the
next services run.

## Libraries

The list is `autolab_services_jellyfin_libraries` in the container-services
role: a name, a Jellyfin type (`movies` or `tvshows`) and a folder under
`media/`. The services run creates each folder, and creates the library when no
library holds its folder yet. It never renames, changes or deletes a library,
so one made or edited in the UI stays as it is. Removing a line from the list
leaves the library in place.

Libraries are split by language (Anime, K-Dramas, C-Dramas, J-Dramas, Desi
Shows for Indian and Pakistani titles, and a movie library for each) so each gets its own row on the home screen and its
own folder for the download apps to file into.

## Not yet seen

The download apps' wiring as code (the clients and root folders set through
each app's API).

A file played on the projector over the home address.

Seerr opened from a TV at home, and a request from it reaching Sonarr.
The public door from outside: a friend's sign-in from mobile data, the admin
refused, a non-US address refused, and a ban after five wrong passwords.
