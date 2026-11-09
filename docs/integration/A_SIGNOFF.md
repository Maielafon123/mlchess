# A-I19 release evidence

Status: **guest preview available; full release withheld**. The signed-off
public guest acceptance covers 4a8b4e32c18ef7822e6ca81065fc1ae6c39a952d
(PR48, exact main 987ba0cf8289a007031e519226eacdab1f8738f7).
The relay candidate passed all seven checks in 42546470390.
Public HTTPS and application service checks passed without VPN access.

| Gate | Status and evidence |
| --- | --- |
| Contracts and route surface | PASS: composed route preflight; 58 golden fixtures after optional provider disclosure. |
| Real game and learning flows | PASS: 21 Compose browser scenarios cover AI, coach, guest challenge, ranked accounts, post-game analysis and learning. Public guest preview 18/18 on trusted HTTPS, including Android and iPhone. |
| Game consistency | PASS: PostgreSQL command/replay, job lease and recovery, matchmaking/cancel and rated timeout races. |
| Google production identity | SKIP: signed local callback, durable one-use state and rotation tested; DNS name and Google web OAuth credentials missing. |
| Coach provider | PASS for verified server-local rules with real Stockfish and offline structured provider tests; live external provider SKIP because no credential is configured. |
| Restore | PASS: a real encrypted off-VPS snapshot restored into disposable PostgreSQL. Continuous production WAL and independent key escrow pending. |
| Supply chain and load | PASS: lockfile audits, image SBOM and Stockfish license/manifest; 8 isolated guests and 64 reads in Compose. |
| Redis recovery | PASS: a real two-phone Compose game continued during broker outage, five unpublished rows persisted, and event IDs reached Redis after restart. |
| Legacy trainer | PASS: isolated legacy regression includes finite loss/backpropagation and legal move masking on synthetic data. A production training run is outside the web deployment. |

No full release tag. Do not enable dev login on the public site. Evidence for
later builds belongs in A_STATUS.md; a route preflight is not approval to enable
additional public capabilities.
