# P3a — ordinary authenticated Evennia client transport

**Status: implemented, tested and merged as
[PR #10](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/10).**
This is the initial network-transport milestone, not a description
of everything implemented since then. [Current state](../STATUS.md).

## Implemented P3a

- The external handler connects via Evennia's ordinary
  `v1.evennia.com` JSON WebSocket protocol
  (`services/ai-handler/src/ox_ai/ports/evennia/client.py`).
- Each nonprivileged account puppets one permitted persistent
  character. `connect`/`ic` precede a nonce-based `oxidentity`
  challenge; a valid account cannot impersonate another character.
- AI actions are normal in-world client commands, not a
  privileged database or Omniscient Game Master API.
- Credentials sent over `ws://` are limited to local loopback.
  Real remote service deployment would require audited `wss://`.
- CI starts a real Evennia portal and drives a separate external
  client process through `look`, `inspect`, speech and denied
  cross-character access.

## Limits at this milestone

The P3a socket is **not** itself a durable world transaction API.
Plain command text is not proof of physical action success. Test
account provisioning (`game/world/transport_probe.py`) creates
throwaway bot identities for CI; it is not production provisioning.

**Subsequent work is complete:** P3b introduced actor-bound physical
receipts and lost-ACK reconciliation; P3c added three independent
clients coordinating a real incident. P4a and P4b added native
Concordia actor choices and a persistent event-driven supervisor.
See [P3b](p3b-durable.md), [P3c](p3c-live-crew.md),
[P4a](p4a-live-cognition.md) and [P4b](p4b-autonomous-watch.md).

**Evidence:** [`ox-p3-live.yml`](../../.github/workflows/ox-p3-live.yml),
[contracts](../../contracts/README.md).
