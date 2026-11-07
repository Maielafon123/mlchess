# Local infrastructure

For the complete private application (web, proxy, API, independent engine worker,
migrations, PostgreSQL and Redis), use [the Compose runbook](compose-runbook.md).
The infrastructure-only legacy setup below is retained for compatibility.

The development stack is intentionally small and reproducible:

```powershell
docker compose --env-file infra/.env.example -f infra/compose.dev.yml up -d
docker compose --env-file infra/.env.example -f infra/compose.dev.yml ps
```

PostgreSQL is exposed on `localhost:55432` and Redis on `localhost:56379`.
The backend can use the values in `infra/.env.example` as its local defaults.

On Windows, keep the Stockfish executable outside the repository and configure
the adapter with its absolute path. Verify the binary before use with:

```powershell
Get-FileHash C:\path\to\stockfish-windows-x86-64-universal.exe -Algorithm SHA256
```

Stop the stack when finished:

```powershell
docker compose --env-file infra/.env.example -f infra/compose.dev.yml down
```
