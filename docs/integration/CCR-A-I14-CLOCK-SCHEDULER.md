# A-I14: persistent game clocks and idle flag fall

Base e20f85923aabf7361658e63c940f14a03d246e59. The user authorized integration
and mobile verification without a separate human review. Existing GameSnapshot,
Clock and game event wire fields remain compatible.

Old: a late HTTP/engine command settles timeout, but an idle timed game can stay
active at zero indefinitely. Friend UI only creates untimed games.

New: an expand-only migration indexes the deadline derived from each active
game's existing authoritative clock, and stores its nondecreasing observed time.
An independent clock worker selects overdue rows with FOR UPDATE SKIP LOCKED and
rechecks the current clock under the game lock. The same timeout transition is
used by HTTP, gameplay worker and scheduler. Result, game version, stopped clock,
event and outbox commit together once. No client clock can settle a result.

The UTC anchor survives restart. The last observed server time is persisted
separately from the old clock JSON, so a backward wall sample does not refund
elapsed time. The browser projects only display time from performance.now and
adopts authoritative snapshots after reconnect. The server assumes a functioning
UTC source for deadline advancement; it does not infer elapsed downtime from a
broken clock. No host time, routing, firewall or VPN change is needed.

Waiting invitations do not run clocks. A normal move applies increment and
indexes the new side's deadline; finishing clears it. Incompatible or corrupt
deadline projections cannot award a win. Active guest links can select an
optional clock; the friend and AI/coach boards display server-projected times.

Tests: exact deadline, increment, backward sample, waiting/acceptance, rollback-
compatible JSON, move vs scheduler row-lock race, concurrent schedulers, idle
expiry after worker restart, timeout without mating material, and two-browser
guest timeout without a follow-up command. Migration rollback uses compatible
application images with additive columns retained or a verified restore.
