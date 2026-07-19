# ---------------------------------------------------------------------------
# Debian 13 automated install preseed
# Used by Packer during the debian-13.pkr.hcl build.
#
# This configures:
#   - Fully automated install (no interactive prompts)
#   - Minimal server installation
#   - Root password and SSH key injection
#   - Cloud-init for post-clone customization
#
# Reference: https://www.debian.org/releases/stable/amd64/apb.html
# ---------------------------------------------------------------------------

# --- Localisation ---
d-i debian-installer/locale              string en_US.UTF-8
d-i keyboard-configuration/xkb-keymap   string us

# --- Network ---
d-i netcfg/choose_interface              select auto
d-i netcfg/dhcp_timeout                  string 60
d-i netcfg/get_hostname                  string debian-template
d-i netcfg/get_domain                    string local

# --- Mirror ---
d-i mirror/country                       string manual
d-i mirror/http/hostname                 string deb.debian.org
d-i mirror/http/directory                string /debian
d-i mirror/http/proxy                    string

# --- Account setup ---
d-i passwd/root-login                    boolean true
d-i passwd/root-password                 password ${root_password}
d-i passwd/root-password-again           password ${root_password}

# Inject SSH public keys for root (from the ssh_public_keys variable).
# late_command runs once; we append all keys in a single shell command.
d-i preseed/late_command                 string \
  in-target sh -c 'mkdir -p /root/.ssh && chmod 700 /root/.ssh && \
  touch /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys && \
  %{ for key in ssh_keys ~} echo ${key} >> /root/.ssh/authorized_keys && \
  %{ endfor ~} chmod 600 /root/.ssh/authorized_keys'

# --- Clock / Time ---
d-i clock/timezone                       string UTC
d-i clock/setup-ntp                      boolean true

# --- Partitioning ---
d-i partman-auto/method                  string regular
d-i partman-lvm/device_remove_lvm        boolean true
d-i partman-md/device_remove_md          boolean true
d-i partman-partitioning/confirm_write_new_label boolean true
d-i partman/choose_partition             select finish
d-i partman/confirm_nooverwrite          boolean true
d-i partman/confirm                      boolean true
d-i partman-auto/choose_recipe           select atomic

# --- Base system ---
d-i base-installer/kernel/image          string linux-image-amd64

# --- Apt setup ---
d-i apt-setup/non-free                   boolean false
d-i apt-setup/contrib                    boolean false
d-i apt-setup/services-select            multiselect security, updates

# --- Package selection ---
tasksel tasksel/first                    multiselect standard
d-i pkgsel/include                       string cloud-init openssh-server
d-i pkgsel/upgrade                       select none

# --- GRUB ---
d-i grub-installer/only_debian           boolean true
d-i grub-installer/bootdev               string default

# --- Final steps ---
d-i finish-install/reboot_in_progress    note
d-i debian-installer/exit/halt           boolean false
d-i debian-installer/exit/poweroff       boolean false
