# Guest preview on the VPS

The guest preview serves mobile AI, coach, learning and unrated challenge games
over trusted HTTPS. Account-only rating is exercised by isolated CI. The IP
preview does not enable Google login and is not the A-I19 release signoff.

Use an exact reviewed merge SHA as MLCHESS_IMAGE_TAG. Build Linux amd64 API,
worker, static-web and gateway images on the development machine using
compose.server.yml. Export only these images; transfer by SSH, verify archive
SHA256 and load them. Transfer tracked infra files for that same SHA into a new
release directory. Do not copy dotenv, datasets, browser traces or .git.
Generate fresh secrets ON the server, never paste or log them.

From /opt/mlchess/releases/EXACT_SHA, which contains infra/:

```sh
python3 -m infra.init_compose_env --server --origin https://PUBLIC_IPV4 --output /opt/mlchess/shared/.env.server.local
MLCHESS_IMAGE_TAG=EXACT_SHA docker compose --env-file /opt/mlchess/shared/.env.server.local -f infra/compose.server.yml -f infra/compose.vps-host.yml config --quiet
MLCHESS_IMAGE_TAG=EXACT_SHA docker compose --env-file /opt/mlchess/shared/.env.server.local -f infra/compose.server.yml -f infra/compose.vps-host.yml up -d --no-build --wait
```

Create release/shared directories with restricted access. Initializer refuses
overwrites and creates mode0600 files. Preserve database/Redis/invitation secrets
on upgrades. Rotating the invitation key voids unused links. Guest sessions last
7days; invite links expire24hours and seat one opponent. Cleared browser cookies
cannot recover an anonymous seat. Never expose development/fake auth publicly.

User update2026-11-09: do not inspect, read, hash, test or modify the VPN.
No VPN checks are a prerequisite. Do not change host routes, sysctls/firewall or
restart host Docker/networking. The VPS overlay creates no Docker networks or
published-port NAT. PostgreSQL55432, Redis56379, API58000 and static-web58080
bind127.0.0.1 only. Gateway alone binds the configured public IP on80/443.
API/worker/static web remain non-root and read-only. Gateway runs with only
NET_BIND_SERVICE capability to bind privileged host ports without changing
host sysctls. Host network sharing trades container network isolation for
avoiding changes to the host's networking; data services remain loopback-only.
Use application-port probes only. If inbound80/443 is blocked externally, report
that blocker; do not change firewall or VPN settings. CPU/RAM limits remain.

Caddy2.11.9 uses Let's Encrypt's shortlived profile, with160-hour IP certificates
and automatic renewal. Preserve tls_data/tls_config volumes. default_sni handles
IP clients that omit SNI behind Docker port mapping. Public acceptance must use
trusted HTTPS without self-signed certificates or ignore-certificate flags.
Sources: [Let's Encrypt](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability),
[Caddy IP support](https://github.com/caddyserver/caddy/issues/7118),
[Caddy TLS](https://caddyserver.com/docs/caddyfile/directives/tls).

Externally verify trusted certificate IP SAN/issuer/expiry, HTTP redirect,
readiness, dev-login404, Secure/HttpOnly/SameSite cookies and no public database
ports. Run guest-only mobile acceptance against the public origin:

```powershell
$env:MLCHESS_LIVE_BASE_URL='https://PUBLIC_IPV4'
pnpm --dir apps/web test:e2e:live --grep '@guest'
```

The full account/dev-login suite runs on isolated CI/local stacks. Guests cannot
use rated games or active-PvP analysis/coaching/takeback. API bounds command body
size/read time, mutation rate, limiter memory and active-game resource quotas.

Google account sign-in requires a DNS name pointing to the application gateway
and a Google Cloud **Web application** OAuth client. Google does not accept a
public IP in an authorized redirect URI. Add exactly
`https://YOUR_DOMAIN/api/v1/auth/oidc/callback` in Google Cloud and set
`MLCHESS_PUBLIC_ORIGIN=https://YOUR_DOMAIN`, `MLCHESS_SITE_ADDRESS=YOUR_DOMAIN`
and `MLCHESS_BIND_ADDRESS=PUBLIC_IPV4` in the private Compose env. Verify
trusted TLS before enabling credentials. Add `MLCHESS_GOOGLE_CLIENT_ID` and
`MLCHESS_GOOGLE_CLIENT_SECRET` only to the private API configuration on the
server. Leave both empty on the current IP preview. Client secrets never belong
in browser environment variables or Git. [Google redirect rules](https://developers.google.com/identity/protocols/oauth2/web-server#uri-validation).

The trusted loopback header is overwritten by Caddy; enable
`MLCHESS_TRUST_LOOPBACK_GATEWAY` only when API ingress is limited to this local
gateway. Do not expose the backend port. Public cookies migrate to
`__Host-mlchess_session`; a rollback to images predating the cookie change
may require visitors who have already migrated to re-establish their session.

Before upgrades, back up PostgreSQL and record current SHA/image IDs. Migrations
are expand-only; rollback compatible application images while retaining schema
and ALL named volumes. Never use down --volumes, prune or destructive downgrade.
Do not claim RPO/RTO or offsite PITR without actual evidence.
