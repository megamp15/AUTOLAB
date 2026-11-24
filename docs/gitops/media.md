---
tags: [gitops, media, jellyfin, aurora, nas, edge]
status: draft
audience: operator
---

# Media

`aurora` is a VM on zima-pve (edge Stack, VMID 303, 4 vCPU, 4 GB, 150 GB on
the HDD). It runs Jellyfin, which plays the films and shows kept on the NAS.
The apps that fetch them (Sonarr, Radarr, Prowlarr, SABnzbd, qBittorrent
behind a VPN) are planned for the same machine and are not there yet.

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

A file played on the projector over the home address.
