# Proxmox VE — Dell XPS 15 9560 (bare metal)

Install Proxmox on the internal storage of a Dell XPS 15 9560 (or similar). After installation the web interface is available at `https://<management-ip>:8006`.

## Requirements

- Dell XPS 15 9560 or comparable hardware
- USB flash drive (minimum 8 GB recommended)
- Proxmox VE ISO from [proxmox.com](https://www.proxmox.com/en/downloads)
- Image writing tool (e.g. [balenaEtcher](https://etcher.balena.io/)) that writes a raw disk image and, where supported, verifies the write

Write the ISO to the USB device using the tool’s documented procedure. Verification reduces the risk of a bad install from marginal USB hardware.

## Firmware (BIOS/UEFI) settings

Exact labels vary by BIOS revision. On many Dell systems, enter setup with **F2** at POST; boot menu is often **F12**.

| Objective | Setting |
|-----------|---------|
| CPU virtualization | Intel VT-x / Virtualization Technology: **Enabled** |
| IOMMU (optional) | VT-d: **Enabled** if PCIe or USB passthrough is required |
| Boot | UEFI mode; external/USB boot **Enabled**. If the USB device does not appear, disable fast-boot options that skip device enumeration |
| Storage mode | If the SSD is presented only as **Intel RST RAID**, disk layout may not match a simple single-disk install. **AHCI** / non-RAID is typically simpler for one disk. Skip changes if the current configuration already works |
| Secure Boot | If the installer will not start, disable Secure Boot for the installation phase; re-enable later if required by policy |

Record firmware changes for rollback and support.

## Installation procedure

1. Write the Proxmox VE ISO to the USB drive.
2. Boot the system from USB (boot menu, e.g. F12 on many Dell units).
3. Run the installer and select the target disk (all data on that disk will be removed).
4. Configure management IP address, gateway, and DNS during the wizard. Use the address you will use for `https://<ip>:8006`.

After reboot, connect to the web UI on **TCP 8006**. The default TLS certificate is self-signed; replace it per Proxmox documentation if needed.

## Post-installation

- **Repositories and updates**: [04-apt-updates-tailscale.md](./04-apt-updates-tailscale.md)
- **Wi‑Fi on the hypervisor**: [02-host-networking-wifi.md](./02-host-networking-wifi.md); step-by-step: [03-post-install-network-runbook.md](./03-post-install-network-runbook.md)

## Related documentation

- [proxmox/README.md](./README.md) — ordered index
- [../README.md](../README.md) — top-level docs index
