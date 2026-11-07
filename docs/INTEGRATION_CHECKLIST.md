# A+B integration checklist

## Contract and deployment

- [ ] deployed API schema versions match the generated client contracts
- [ ] A-015 mounts game, coach and learning routers
- [ ] A-016 migrations and persistence are applied
- [ ] A-006 auth/session and mode guards are enabled
- [ ] A-011 queue worker is processing coach jobs
- [ ] A-014 analysis reader/result stream is available

## Four play modes

- [ ] solo: create/get/move/resign and stale-version rollback
- [ ] AI: profile/side, engine pending, takeback and stale result rejection
- [ ] coach: automatic observation after accepted human move and five hint levels
- [ ] friend/rated: two browser sessions, presence, clocks, invite/matchmaking,
      resign/draw/result

## Learning demo

- [ ] lesson source/license fields render and unsafe content is sanitized
- [ ] puzzle grading ignores client correctness and duplicate attempts are safe
- [ ] progress schedule is deterministic and export/delete boundaries work
- [ ] verified mistakes generate only legal, owned, PvP exercises

## Sign-off evidence

- [ ] frontend typecheck/unit/build/E2E artifacts attached
- [ ] backend unit/integration/contract artifacts attached
- [ ] invalid, slow and unavailable provider cases leave the board usable
- [ ] no provider keys or user secrets appear in browser bundles/logs
- [ ] privacy notice approved for cloud coach mode
