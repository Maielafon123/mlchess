# A-I19 release evidence

Status: **guest preview available; full release withheld**. The signed-off
public guest image is 4670d1553d79599b23b114429151d0c4baa0d809 (PR45);
the exact main commit is caa5ee92f1feb8f6b7e12e3291ea55279c409ba6.
Public HTTPS and application service checks passed without VPN access.

| Gate | Status and evidence |
| --- | --- |
| Contracts and route surface | PASS: runtime route preflight; 57 golden fixtures after optional OIDC. |
| Real game and learning flows | PASS: PostgreSQL and real Compose browsers cover AI, coach, guest challenge, ranked accounts and learning. Public guest preview 17/17 on trusted HTTPS, including Android and iPhone. |
| Game consistency | PASS: PostgreSQL command/replay, job lease and recovery, matchmaking/cancel and rated timeout races. |
| Google production identity | SKIP: signed local callback, durable one-use state and rotation tested; DNS name and Google web OAuth credentials missing. |
| Coach provider | PASS for verified server-local rules with real Stockfish; SKIP for remote LLM because no provider credential is configured. |
| Restore | PASS: a real encrypted off-VPS snapshot restored into disposable PostgreSQL. Continuous production WAL and independent key escrow pending. |
| Supply chain and load | New CI gates run lockfile audits, per-image SBOM and license inventory, isolated WAL restore, and a concurrent session smoke. Record exact merge results before promoting images. |
| Legacy trainer | Existing isolated legacy regression preserved. A production training run is not covered by the web deployment. |

No full release tag. Do not enable dev login on the public site. Evidence for
later builds belongs in A_STATUS.md; a route preflight is not approval to enable
additional public capabilities.
