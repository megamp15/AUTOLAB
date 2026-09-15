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
d-i passwd/make-user                     boolean false
d-i passwd/root-login                    boolean true
d-i passwd/root-password                 password ${root_password}
d-i passwd/root-password-again           password ${root_password}

# Inject SSH public keys for root (from the ssh_public_keys variable). jsonencode
# keeps key material safe inside the single-quoted late_command shell.
# late_command runs once; we append all keys in a single shell command.
d-i preseed/late_command                 string \
  in-target sh -c 'mkdir -p /root/.ssh && chmod 700 /root/.ssh && \
  touch /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys && \
  %{ for key in ssh_keys ~} echo ${jsonencode(key)} >> /root/.ssh/authorized_keys && \
  %{ endfor ~} chmod 600 /root/.ssh/authorized_keys && \
  mkdir -p /etc/ssh/sshd_config.d && printf "%s\n" "PermitRootLogin yes" "PasswordAuthentication yes" > /etc/ssh/sshd_config.d/packer-root-password.conf'

# --- Clock / Time ---
d-i clock/timezone                       string UTC
d-i clock/setup-ntp                      boolean true

# --- Partitioning ---
#
# A single root partition filling the disk, and deliberately no swap partition.
#
# The stock `atomic` recipe lays down root, an extended partition and swap — in
# that order. growpart can only extend a partition with free space immediately
# after it, so swap sitting behind root makes root permanently unresizable.
# Raising disk_size_gb then grows the virtual disk while the guest filesystem
# stays exactly as large as the day it was built, and cloud-init reports
# "Resized root filesystem" while doing nothing useful, because resize2fs did
# grow the filesystem to fill its (unchanged) partition.
#
# With root last, cloud-init's growpart extends the partition and resize2fs
# follows, so disk_size_gb in machines.auto.tfvars means what it says.
#
# Swap, if a machine needs it, belongs in a swapfile: resizable, movable, and
# not an obstacle to the partition it sits behind.
d-i partman-auto/method                  string regular
d-i partman-lvm/device_remove_lvm        boolean true
d-i partman-md/device_remove_md          boolean true
d-i partman-partitioning/confirm_write_new_label boolean true
d-i partman/choose_partition             select finish
d-i partman/confirm_nooverwrite          boolean true
d-i partman/confirm                      boolean true

d-i partman-auto/expert_recipe           string                       \
      autolab-root ::                                                 \
              2048 2048 -1 ext4                                       \
                      $primary{ } $bootable{ }                        \
                      method{ format } format{ }                      \
                      use_filesystem{ } filesystem{ ext4 }            \
                      mountpoint{ / }                                 \
              .
d-i partman-auto/choose_recipe           select autolab-root

# Building without swap is intentional, not an oversight the installer should
# stop to ask about.
d-i partman-basicfilesystems/no_swap     boolean false

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
