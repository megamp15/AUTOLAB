# ---------------------------------------------------------------------------
# cloud-init — composes cloud-init user-data from base config and optional modules.
#
# Base cloud-init is always included. Tailscale and any extra runcmd entries
# are composed into a single cloud-config document.
# ---------------------------------------------------------------------------

variable "admin_username" {
  description = "Initial non-root admin user created by cloud-init."
  type        = string
  default     = "autolab"
}

variable "ssh_public_keys" {
  description = "Public SSH keys injected at provisioning time. Never put private keys here."
  type        = list(string)
  default     = []
}

variable "hostname" {
  description = "Hostname applied by cloud-init."
  type        = string
}

variable "tailscale_auth_key" {
  description = "Tailscale auth key for VMs to join the tailnet on first boot. Empty string skips Tailscale enrollment."
  type        = string
  default     = ""
  sensitive   = true
}

variable "tailscale_retry_attempts" {
  description = "Number of times to retry the Tailscale join command on failure."
  type        = number
  default     = 5
}

variable "tailscale_retry_delay_seconds" {
  description = "Seconds to wait between Tailscale join retry attempts."
  type        = number
  default     = 10
}

variable "tailscale_accept_routes" {
  description = "Pass --accept-routes to tailscale up."
  type        = bool
  default     = true
}

variable "tailscale_extra_args" {
  description = "Additional CLI arguments appended to tailscale up."
  type        = list(string)
  default     = []
}

variable "tailscale_log_path" {
  description = "Path on the VM where Tailscale install/join output is logged."
  type        = string
  default     = "/var/log/cloud-init-tailscale.log"
}

variable "extra_runcmd" {
  description = "Additional runcmd entries appended after the base cloud-init commands."
  type        = list(string)
  default     = []
}
