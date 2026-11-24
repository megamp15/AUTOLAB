---
tags: [gitops, media, jellyfin, aurora, nas, edge]
status: draft
audience: operator
---

# Media

`aurora` is a VM on zima-pve (edge Stack, VMID 303, 4 vCPU, 4 GB, 150 GB on
the HDD). It runs Jellyfin, which plays the films and shows kept on the NAS, and the
apps that fetch them: Prowlarr, Sonarr, Radarr, Bazarr, SABnzbd, and
qBittorrent behind Gluetun and Mullvad.

## The download apps

| app | name on the tailnet | does |
|---|---|---|
| Prowlarr | `prowlarr.lab.<zone>` | holds the indexers and hands them to Sonarr and Radarr |
| Sonarr | `sonarr.lab.<zone>` | finds series (shows, anime, dramas) and files them into their library folder |
| Radarr | `radarr.lab.<zone>` | the same for films |
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
/data/usenet/complete          SABnzbd's finished downloads
/data/torrents                 qBittorrent's downloads
```

One tree on one share means an import is a rename (Usenet) or a hardlink
(torrents, which keep seeding), never a copy. SABnzbd unpacks on aurora's own
disk (`/opt/autolab/services/sabnzbd/incomplete`) and moves the finished file
to the share once.

## Who reaches Jellyfin, and how

| from | address | what is in front |
|---|---|---|
| a device at home (the projector, a TV) | `http://<aurora's home address>:8096` | Jellyfin's sign-in |
| a device on the tailnet | `https://jellyfin.lab.<zone>` | Jellyfin's sign-in |
| the internet | nothing | no public name |

The home address exists because the projector and the TVs are not on the
tailnet. Docker publishes 8096 and UDP 7359 on the machine's home address,
and aurora's `firewall_rules` open both to the home network only. The
docker-host role turns those rules into `DOCKER-USER` exceptions, because
Docker's own rules would otherwise send a published port past ufw. Any other
published port is still dropped on the home network. UDP 7359 lets a Jellyfin
app at home find the server without being given an address.

There is no passkey in front of either name. Jellyfin's apps on a phone or a
TV cannot answer a passkey page.

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

## First run

Jellyfin starts with no users. Open it on the tailnet name, make the
administrator account in its setup pages, and skip adding libraries.

Then make an API key under Dashboard, API Keys, named `autolab`, and store it
as the `JELLYFIN_API_KEY` secret. The next services run creates the libraries.

### The download apps

Their wiring is not code yet; set it in each app's UI:

1. SABnzbd: its first-run wizard asks for the Usenet server. Categories
   `tv` and `movies`, completed folder `/data/usenet/complete`, temporary
   folder `/incomplete`.
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

## Libraries

The list is `autolab_services_jellyfin_libraries` in the container-services
role: a name, a Jellyfin type (`movies` or `tvshows`) and a folder under
`media/`. The services run creates each folder, and creates the library when no
library holds its folder yet. It never renames, changes or deletes a library,
so one made or edited in the UI stays as it is. Removing a line from the list
leaves the library in place.

Libraries are split by language (Anime, K-Dramas, C-Dramas, J-Dramas, and a
movie library for each) so each gets its own row on the home screen and its
own folder for the download apps to file into.

## Not yet seen

The download apps' wiring as code (Recyclarr for the TRaSH profiles, and the
clients and root folders set through each app's API).

A file played on the projector over the home address.
