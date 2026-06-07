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
  tailscale_accept_routes_flag = var.tailscale_accept_routes ? " --accept-routes" : ""
  tailscale_extra_args_str     = length(var.tailscale_extra_args) > 0 ? " ${join(" ", var.tailscale_extra_args)}" : ""

  tailscale_runcmd = var.tailscale_auth_key != "" ? [
    "curl -fsSL https://tailscale.com/install.sh | sh 2>&1 | tee -a ${var.tailscale_log_path}",
    <<EOT
for i in $(seq 1 ${var.tailscale_retry_attempts}); do
  if tailscale up --authkey=${var.tailscale_auth_key}${local.tailscale_accept_routes_flag} --hostname=${var.hostname}${local.tailscale_extra_args_str} 2>&1 | tee -a ${var.tailscale_log_path}; then
    echo "Tailscale joined successfully" | tee -a ${var.tailscale_log_path}
    break
  fi
  echo "Tailscale join attempt $i failed, retrying in ${var.tailscale_retry_delay_seconds} seconds..." | tee -a ${var.tailscale_log_path}
  sleep ${var.tailscale_retry_delay_seconds}
done
EOT
  ] : []

  cloud_config = {
    hostname = var.hostname
    users = [
      {
        name                = var.admin_username
        sudo                = "ALL=(ALL) NOPASSWD:ALL"
        shell               = "/bin/bash"
        lock_passwd         = true
        ssh_authorized_keys = var.ssh_public_keys
      }
    ]
    packages = ["qemu-guest-agent"]
    runcmd   = concat(local.base_runcmd, local.tailscale_runcmd, var.extra_runcmd)
  }

  user_data = "#cloud-config\n${yamlencode(local.cloud_config)}"
}
