# A-003: reproducible contract pipeline (review candidate)

Depends on the A-001/A-002 schema proposals. This adds no HTTP service, DB,
Stockfish process or B-owned module. The first contract gate remains pending
A+B review and hosted CI. B-001 coach/learning schema fragments may be added by
their owner later; the assembler discovers domain `*.yaml` schema documents and
`http.v1.yaml` operation fragments without hand-copying interfaces.

Install with Python 3.12 and Node 24, from a clean checkout:

```bash
python -m pip install -r contracts/requirements.txt
npm --prefix contracts ci --ignore-scripts --no-audit --no-fund
make contract-check
make contract-compat
```

Use an activated virtual environment. Direct tool dependencies are pinned in
`requirements.txt`, with transitive constraints in `requirements.lock` captured
from a clean Python 3.12 Linux environment. Node dependencies and integrity
hashes are pinned in `package-lock.json`. No frontend manifest is modified.
Cross-platform installs may need platform-specific dependency additions; the
reproducibility reference is Python 3.12/Linux + Node 24, matching contract CI.
Legacy tests require the separately documented ML dependencies; the new contract
pipeline itself does not install PyTorch or need a GPU.

## Sources and generated files

Edit domain schema YAML and HTTP fragments, then run `make contract-generate`.
The generator assembles and validates OpenAPI 3.1 entirely offline, resolves
cross-domain references locally, and rejects duplicate names/routes/operation
IDs. There is no schema fetch, runtime HTTP call or introspection of app routers.

It uses datamodel-code-generator 0.36.0 for Pydantic 2.12.5, openapi-typescript
7.10.1 for TypeScript, and openapi-fetch 0.15.0 for the typed client. Versions of
formatters are constrained too. Timestamp-free headers, stable ordering and
fixed formatter settings make generation repeatable from a different directory.

Generated outputs:

- `contracts/openapi.generated.yaml`: seven proposed REST path templates,
  seven operations, common/game/analysis/event schema components, source map.
- `backend/app/infra/generated/contracts.py`: Python models from schema types.
- `contracts/generated/api.d.ts`: REST paths and shared/event TypeScript types.
- `contracts/generated/validation.schema.json`: full JSON Schema constraints.
- `contracts/generated/fixtures.consumer.ts`: all golden payloads compiled as
  literal values against their generated types, including every event variant.

`client.ts` is a generic typed fetch factory, not a parallel interface. Its
requests and responses derive from generated `paths`. The SDK preserves
same-origin credentials by default; mutating operation signatures require CSRF,
and game/analysis creation also require an idempotency header. A fake-fetch test
checks request construction and structured 409 errors without network calls.
Runtime server-side Origin/session/CSRF authorization is still A-006/A-022 work.

All paths are explicitly marked proposed. Cookie spelling
`__Host-mlchess_session` is a review candidate; auth configuration can settle it
before acceptance. Adding HTTP documentation does not implement the endpoints.

## Full validation versus wire types

Ordinary Python/TS generators cannot express every JSON Schema `if/then`,
format, `contains`, uniqueness or chess invariant. Python generation uses a
type-only projection that retains object fields, enums, bounds and ordinary
unions, while leaving full conditional constraints in the generated validation
bundle. UUID/FEN/UTC remain wire strings, avoiding implicit Python conversions
or incompatible format+pattern constraints.

Backend consumers must use the schema boundary:

```python
from backend.app.infra.generated.contracts import SubmitMoveV1
from contracts.runtime import parse_contract

command = parse_contract(SubmitMoveV1, raw_json_payload)
```

`parse_contract` first checks the complete bundled schema and formats, then
parses the generated Pydantic type. This retains required nullable fields,
mode restrictions, mate/cp rules and safe integer checks. Raw generated model
constructors or TS types alone are not substitutes. Tests verify every fixture
round-trips without changing its JSON and that invalid cross-field cases fail.
Chess PV/evidence fixture checks remain in `contracts/validate.py`; application
domain legality, authorization and revision checks are separate release gates.

## Drift and compatibility

`python -m contracts.tooling.generate --check` generates into a temporary
location and compares every output byte-for-byte. It fails on a missing file,
stale schema, manual generated edit, or codegen/formatter drift, and never edits
workspace files in check mode. A negative test intentionally changes a generated
artifact in a disposable checkout and verifies failure without repairing it.

`python -m contracts.tooling.compatibility --base-ref <commit-or-ref>` compares
against the base commit's published generated specification. Existing v1 schema,
route, type, enum, required-field, constraint or security changes fail. New
optional properties, independent schemas and new routes can be added; preserve
existing v1 interfaces when introducing v2. The gate is intentionally conservative
for any change it cannot prove safe. Documentation changes alone do not fail.
This is a structural check, not a proof that API semantics remain compatible.
Closed-schema consumers may also need regeneration for new optional properties.

The initial base has no generated contract, so the checker explicitly reports
that no accepted baseline exists and review is required. It does not mark the
proposal accepted. Subsequent CI uses the PR base SHA or push predecessor,
fetching full history. Tests demonstrate rejection of removed fields/routes,
new required fields/enums, changed types, relaxed mate constraints and removed
authentication. Human review remains required for semantic/security changes.

## Current handoff

A-001, A-002 and A-003 are stacked local commits while GitHub write access is
pending. Their PRs must be opened separately, reviewed and pass CI before the
contract gate can be called Done. No migration applies at this stage. These
artifacts supply B-004…B-009 game mocks and B-001/B-010 analysis/event mocks;
frontend integration can import the generated types without editing A-owned
schema definitions.
