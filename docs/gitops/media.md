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
tailnet. Docker publishes that port on the machine's home address only, and
Docker's rules sit ahead of ufw's, so every device at home can reach it and
`ufw status` does not show it. UDP 7359 is published the same way, so a
Jellyfin app at home finds the server without being given an address.

There is no passkey in front of either name. Jellyfin's apps on a phone or a
TV cannot answer a passkey page.

## Where things are

| thing | where | why |
|---|---|---|
| films and shows | NAS, `/mnt/aurora/media-stack/media/{movies,tv}` (share `/volume1/aurora`, NFS) | they outlive the VM; Jellyfin mounts them read-only |
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
administrator account in its setup pages, and add two libraries: Movies at
`/data/media/movies` and Shows at `/data/media/tv`.

## Not yet seen

A file played on the projector over the home address.
