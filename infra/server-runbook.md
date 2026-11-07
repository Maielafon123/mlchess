# Guest preview on the VPS

This serves real AI games and unrated guest challenge links, including mobile
Chromium/WebKit. It is a limited guest preview, not A-I19 signoff for all modes.
Google OIDC, analysis/coach/learning integration, rated matchmaking, WebSocket
replay and independently tested offsite PITR remain separate release tasks.

Use an exact reviewed merge SHA as MLCHESS_IMAGE_TAG. Build Linux amd64 API,
worker, static-web and gateway images on the development machine using
compose.server.yml. Export only these images; transfer by SSH, verify archive
SHA256 and load them. Transfer tracked infra files for that same SHA into a new
release directory. Do not copy dotenv, datasets, browser traces or .git.
Generate fresh secrets ON the server, never paste or log them.

From /opt/mlchess/releases/EXACT_SHA, which contains infra/:

```sh
python3 -m infra.init_compose_env --server --origin https://PUBLIC_IPV4 --output /opt/mlchess/shared/.env.server.local
MLCHESS_IMAGE_TAG=EXACT_SHA docker compose --env-file /opt/mlchess/shared/.env.server.local -f infra/compose.server.yml config --quiet
MLCHESS_IMAGE_TAG=EXACT_SHA docker compose --env-file /opt/mlchess/shared/.env.server.local -f infra/compose.server.yml up -d --no-build --wait
```

Create release/shared directories with restricted access. Initializer refuses
overwrites and creates mode0600 files. Preserve database/Redis/invitation secrets
on upgrades. Rotating the invitation key voids unused links. Guest sessions last
7days; invite links expire24hours and seat one opponent. Cleared browser cookies
cannot recover an anonymous seat. Never expose development/fake auth publicly.

Only80/tcp and443/tcp+udp are published. PostgreSQL/Redis have no host ports.
API/worker/static web run non-root with read-only filesystems. CPU/RAM limits
leave VPN capacity. CHECK network overlap before starting. Do not modify VPN
files, interfaces, routes, sysctls, firewall policy or restart host Docker/network.
Compare protected VPN config hashes/interface/route before and after; do not
print private configuration or peer credentials.

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

Before upgrades, back up PostgreSQL and record current SHA/image IDs. Migrations
are expand-only; rollback compatible application images while retaining schema
and ALL named volumes. Never use down --volumes, prune or destructive downgrade.
Do not claim RPO/RTO or offsite PITR without actual evidence.
