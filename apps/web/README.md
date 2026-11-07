# MLChess Web

Developer B web foundation for architecture v1.

## Local commands

```bash
pnpm install
pnpm run dev
pnpm run lint
pnpm run test
pnpm run build
pnpm run test:e2e
```

This scaffold intentionally has no authoritative chess state or ad-hoc API. The play route is a UI shell waiting for the A-owned `GameSnapshotV1` and related contracts. Browser state is limited to presentation and locale selection.
