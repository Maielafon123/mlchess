# CCR-B-I01-CSRF — Browser CSRF handshake

## B consumer implementation

`apps/web/src/api/client.ts` sends same-origin cookies and, for mutations, reads
the configured CSRF cookie (`VITE_CSRF_COOKIE_NAME`, default `mlchess_csrf`) and
copies it into `X-CSRF-Token`. Callers can inject a token provider in tests.

## A confirmation required

Confirm the production cookie name, path/domain, `HttpOnly` policy, rotation
behavior and whether the header must be obtained through a dedicated handshake
endpoint instead of a readable cookie. B will change only this adapter once the
published contract is authoritative.

## Consumer tests

- mutation includes CSRF only when a provider returns a token;
- GET never sends a CSRF header;
- caller-supplied idempotency key is preserved across retries;
- request timeout/abort does not leak credentials or retry with a new key.

## Blocked tickets

B-I01, B-I03, B-I05, B-I18, B-I19, B-I20.
