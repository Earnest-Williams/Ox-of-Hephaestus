# G19 — integrated casualty, restart and transactional acceptance

**Branch:** `g19-complete-ship-systems` · **PR:** #138 (draft, unmerged)
**Engineering baseline:** 29 October 2026
**Original source:** the 421-space, 517-link, 808-piece v0.5 candidate as installed
in Evennia; the original 133 pressure cells remain unchanged.

## Accepted runtime and evidence

The final integrated campaign was developed across the runtime commits
`33fb98f9` (four installed campaigns) and `95073273` (independent-process
persistent-world probe). The workflow was corrected and the latter probe
accepted on code head **`0ed5f0d3`** via
[GitHub Actions run #40889821371](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40889821371).
**All four jobs passed**: pure conservation/fault recovery, installed
multi-system campaign, existing adjacent-system compatibility, and the
two-process persistent-world restart. After the probe's exception handling
was made specific to the expected rejected pressure reset, the **exact
updated runtime `32cb309d` also passed all four jobs** in
[run #40890643600](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40890643600).
The separate fast PR and documentation checks also passed.

The prior compound cargo-sector and three-crew casualty campaign was green
on [run #40877870627](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40877870627):
four jobs, including five adjacent EVA, hull, rescue, medical, and
commercial movement scenarios.

## Bounded installed-world campaign

`game/world/tests/test_installed_ship_g19_final_campaign.py` uses actual
installed equipment records, doors, gas pressure cells, crew work receipts,
water ledgers, original feeder and a continuous monotonic game clock.

1. **Simultaneous failures:** one observed cargo-sector shell leak with its
   own open rated hatch; a finite HAB-01 fire burning actual finite fuel and
   producing smoke; one severed real main-generator electrical edge; and
   existing physically inventoried contaminated water. All systems advance
   on the same ten-second tick clock. The test verifies loss-to-space,
   HAB smoke/fuel, genuine reduced electrical availability, contamination
   quarantine, drum coast inhibit, and gallery isolation while the
   sector continues losing only its own gas.
2. **Durable reentry and downtime:** re-instantiating the canonical Evennia
   world and re-running commissioning do not erase lost mass, refill gas,
   change original hatch settings, duplicate a worker's receipted command or
   reset the original epoch. A 230-second game-time backlog is caught up in
   four bounded steps (60/60/60/50), then an equal-time call does nothing.
3. **Tick transaction rollback:** an injected exception on the third genuine
   ten-second cargo substep aborts the entire current one-minute world tick.
   Re-read persisted pressure, fuel inventory, event count, cargo ledger and
   game time remain exactly at their pre-tick values. Retrying advances once
   and emits no duplicate shell loss.
4. **Persistent script singleton:** a commissioned existing Evennia clock
   script may be rebound repeatedly without creating a second script or
   resetting the ship's original atmosphere.

The neighboring regression job independently checks original generator
brownout, dark instrument failure-latch retention, and the three-real-crew
timed rescue after a cargo breach.

## Actual separate-Python-process persistence test

`game/world/g19_process_recovery.py` has two independently invoked entry
points. It is guarded by `OX_G19_RESTART_CI=1` and refuses any database
outside its named disposable SQLite file under the GitHub Actions runner's
temporary directory. It does not touch a deployed Ox database.

- **Process A** migrates a freshly created disposable schema, installs the
  physical ship, commissions original G19 systems, signs a real cargo-sector
  hatch work receipt, opens the original rated door, introduces a finite
  observed cargo breach, a HAB fire, and water contamination, advances a
  minute and exits. Result: `last_s=1060`, cargo-shell loss **18 kg**,
  one durable receipt and one persistent script.
- **Process B** starts a *new Python interpreter*. It reads that same
  SQLite database, proves the pre-existing mass loss, burned fuel, original
  gallery mass, contamination quarantine, event count, script identity and
  unmodified receipted action; refuses a false rearm/pressure reset; and
  catches up 230 seconds in four bounded ticks. Result: `last_s=1290`,
  cumulative cargo-shell loss **87 kg**, one persistent script and one
  original receipt. A same-time retry is a no-op.

This is a genuine **cross-interpreter persistent database recovery**.
It is not a controlled stop/restart of an actively running Twisted/Evennia
daemon with concurrent connected clients. That broader operational boundary
is not asserted by these tests.

## What this does and does not close

**Now demonstrated** for the tested G19 configuration: multi-system
causality on the same physical clock; bounded recovery of downtime;
re-commissioning without damage resets; exactly-once work receipts;
all-or-nothing world transactions under a late injected failure;
physical-script singleton rebind; and conservation over an actual
separate-process database handoff.

**Still distinct from full G19 release closure:** comprehensive
equipment-family coverage signoff, every high-severity interlock/fault
sequence, full persistent daemon restart in a deployed environment, and
broader independent long-duration player/AI acceptance. These remain
engineering judgment/acceptance activities, not reasons to fabricate
new hardware or introduce a NASA-grade solver.

The **40-crew voyage remains explicitly excluded** from this development
pass. PR #138 remains draft and unmerged until its remaining G19 gates
are signed off.
