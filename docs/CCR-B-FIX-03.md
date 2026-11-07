# CCR-B-FIX-03 — Game client contract alignment

## Implemented in B

- `GameApi.create()` sends `mode` plus mandatory `time_control`.
- AI creation sends `mode: ai`, `human_color`, `ai_profile` and `time_control`.
- Move responses accept `MoveAcceptedV1` and unwrap its authoritative snapshot.
- Random AI side is resolved once with browser CSPRNG before creation.

## A confirmation required

Confirm the deployed route and response envelope remain:

- `POST /api/v1/games`
- `POST /api/v1/games/{game_id}/moves`
- `MoveAcceptedV1.snapshot` as the authoritative client state

If the generated client is available, replace these temporary B-owned types with the generated export. Do not silently change the response envelope in the UI adapter.

## Blocked tickets

B-008, B-009, B-014, B-016, B-017, B-025.
