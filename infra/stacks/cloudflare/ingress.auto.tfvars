zone_name   = "pmahir.space"
tunnel_name = "autolab"

# Three names, one origin. Traefik on horizon routes by Host header; Pocket ID
# answers auth. Adding a public service is a line here plus its Traefik route.
public_hostnames = {
  home    = { comment = "the homepage, behind the login" }
  grafana = { comment = "Grafana, logs in via Pocket ID" }
  auth    = { comment = "Pocket ID, the login page itself" }
}
