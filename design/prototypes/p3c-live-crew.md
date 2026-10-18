# P3c — three real Evennia characters cooperate on P-01

**Status: implemented, tested and merged as
[PR #12](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/12).**
This phase uses **deterministic role policies** over three
real independently authenticated clients, not three
open-ended language-model deliberations.
[Current implementation](../STATUS.md).

## Real-world acceptance path

Lin alone receives the world-issued Bridge coolant alarm. She
radios engineering; Ari inspects P-01 in person and uses the
dependency-free GOAP planner to isolate and repair the
actual pump. Iona independently inspects the repaired
equipment and grants the world-validated chief release.
Ari commissions, re-inspects for normal pressure and reports
resolution to the Bridge.

The world's watch roster then advances the **P3 test's
synthetic clock**, enabling a co-located handover. Ari offers
and Iona accepts, transferring *actual* duty authority.
Every private `ox_event` has exactly one recipient, and
`oxinbox` can replay only events addressed to the logging-in
character. Physical commands are checked by Evennia, never
by a model's promised effects.

Tests check unauthorized/remote access, release prerequisites,
private event scope, replay and the independent persisted
SQLite pump/roster outcomes. The full-server
[`ox-p3-three-crew.yml`](../../.github/workflows/ox-p3-three-crew.yml)
run demonstrates this exact authored episode.

## What came afterward

The P3 test originally jumped its synthetic clock when the
first incident closed. **P4b replaces that shortcut in its
new acceptance test with the world-owned `ShipDutyClock`
Script**, and allows a second pump fault after Iona assumes
watch. At that point **Ari** becomes the independent
safety reviewer, avoiding self-authorization. P4a first
added native Concordia `EntityAgentWithLogging` instances
for all three characters with finite decisions.

See [P4a](p4a-live-cognition.md),
[P4b](p4b-autonomous-watch.md) and
[game mechanics](../../game/README.md). P3c alone did not
prove unscripted cooperation or a persistent handler daemon.
