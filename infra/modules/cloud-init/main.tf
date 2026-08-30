# ---------------------------------------------------------------------------
# cloud-init — composes cloud-init user-data from base config and optional extras.
#
# Base cloud-init (hostname, user, SSH keys, qemu-guest-agent) is always
# included. Optional Tailscale setup and extra commands are appended into a
# single cloud-config document.
# ---------------------------------------------------------------------------

locals {
  base_runcmd = [
    "systemctl enable qemu-guest-agent",
    "systemctl start qemu-guest-agent",
  ]

  # ---- Tailscale command composition ----
  # Cloud-init owns initial enrollment and retry; the Builder only upgrades the installed client later.
  tailscale_accept_routes_flag = var.tailscale_accept_routes ? " --accept-routes" : ""
  tailscale_extra_args_str     = length(var.tailscale_extra_args) > 0 ? " ${join(" ", var.tailscale_extra_args)}" : ""

  tailscale_runcmd = var.tailscale_auth_key != "" ? [
    "curl -fsSL https://tailscale.com/install.sh | sh 2>&1 | tee -a ${var.tailscale_log_path}",
    <<EOT
for i in $(seq 1 ${var.tailscale_retry_attempts}); do
  if tailscale up --auth-key=${var.tailscale_auth_key}${local.tailscale_accept_routes_flag} --hostname=${var.hostname}${local.tailscale_extra_args_str} >> ${var.tailscale_log_path} 2>&1; then
    tailscale_joined=true
    echo "Tailscale joined successfully" | tee -a ${var.tailscale_log_path}
    break
  fi
  echo "Tailscale join attempt $i failed, retrying in ${var.tailscale_retry_delay_seconds} seconds..." | tee -a ${var.tailscale_log_path}
  sleep ${var.tailscale_retry_delay_seconds}
done
if [ "$${tailscale_joined:-false}" != "true" ]; then
  echo "Tailscale enrollment failed after ${var.tailscale_retry_attempts} attempts." | tee -a ${var.tailscale_log_path}
  exit 1
fi
if ! tailscale wait --timeout=60s >> ${var.tailscale_log_path} 2>&1; then
  echo "Tailscale enrollment verification timed out or failed while waiting for connectivity." | tee -a ${var.tailscale_log_path}
  exit 1
fi
if ! tailscale ip -4 >> ${var.tailscale_log_path} 2>&1; then
  echo "Tailscale enrollment verification failed while reading the IPv4 address." | tee -a ${var.tailscale_log_path}
  exit 1
fi
echo "Tailscale enrollment verified successfully." | tee -a ${var.tailscale_log_path}
if ! tailscale set --ssh=true >> ${var.tailscale_log_path} 2>&1; then
  echo "Failed to enable Tailscale SSH." | tee -a ${var.tailscale_log_path}
  exit 1
fi
echo "Tailscale SSH enabled successfully." | tee -a ${var.tailscale_log_path}
EOT
  ] : []

  cloud_config = {
    hostname   = var.hostname
    ssh_pwauth = false
    users = [
      {
        name                = var.admin_username
        sudo                = "ALL=(ALL) NOPASSWD:ALL"
        shell               = "/bin/bash"
        lock_passwd         = true
        ssh_authorized_keys = var.ssh_public_keys
      }
    ]
    packages = ["qemu-guest-agent", "curl", "ca-certificates"]
    runcmd   = concat(local.base_runcmd, local.tailscale_runcmd, var.extra_runcmd)
  }

  user_data = "#cloud-config\n${yamlencode(local.cloud_config)}"
}
