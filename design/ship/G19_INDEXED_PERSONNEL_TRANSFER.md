# G19 — installed indexed personnel transfer machinery

**Status:** **bounded indexed personnel subsystem accepted** on 26 October 2026; draft PR #138 remains unmerged. The 40-crew autonomous voyage is excluded from this engineering phase. This is a causal game-world system for a repeatedly refitted working freighter, not a spacecraft certification or moving-frame structural analysis.

## Physical contract

The canonical v0.5 topology already provides **nine separate rated indexed personnel connections**. The G19 runtime does not manufacture new rooms or accept unclassified shortcuts. The six cargo drums DR-01 through DR-06 each connect the fixed `DR-xx-SERVICE-LOCK` to the rotating `DR-xx-HUB` through `ACC-DR-xx-LOCK-ROT` with **180 seconds** traverse time, and retain their own fixed-end pressure doors `ACC-DR-xx-LOCK-FIX`.

HAB has two independently installed stations with local drives and fixed/rotary collars: `IX-A-CAPSULE` to `IX-A-ROT-VEST` through `ACC-IX-A-ROT`, and `IX-B-CAPSULE` to `IX-B-ROT-VEST` through `ACC-IX-B-ROT`. Both take **300 seconds** and independently retain `ACC-IX-A-FIX` and `ACC-IX-B-FIX` fixed-side pressure hatches. The work rotor has a separate ninth link, `ACC-WR-IX-HUB`, from the `WR-IX-CAPSULE` to `WR-HUB`, rated at **20 seconds**, with its own fixed hatch `ACC-WR-FIXED-IX`. It uses the actual `WR-INDEXER` and `WR-ROT-PWR-IF` equipment and the independent `WR-01` hardlock and brake. The fixed-side hatch operates only with the moving collar retracted.

The two HAB stations share HAB's active rotary capture allocation: the model intentionally permits only one active HAB-indexed transfer at a time, rather than inventing redundant simultaneous operating power or motion authority.

The original `ship_motion_machinery.py` still owns rotor angular state, target RPM, brake, hardlock, angular phase, freight exclusion, bearing state and electrical actuation. The new `ship_indexed_personnel.py` is only a deterministic finite-time job contract; the installed Evennia clock owns the persisted jobs, rotor state, actual gas cells, crew locations, access conditions, machinery and command receipts.

## Boarding and transfer

1. A qualified engineer actuates a real fixed-side personnel hatch through `oxplant <uuid> hatch <ACC-...-FIX> open`, after verifying sound hardware, safe pressure and gas on both sides, and a fully **retracted** rotary collar. This is not a freight door, ordinary HAB bridge hatch or EVA outer hatch.
2. The traveller crosses that actual fixed-side canonical exit. An engineer closes the fixed hatch and operates the drum personnel indexer (`rotor DR-01 passenger_extend`) or the workshop rotor (`rotor WR-01 passenger_extend`), or selects the appropriate HAB station (`rotor HAB passenger_extend:A` or `passenger_extend:B`). The rotor must be stopped, aligned to its indexing datum, braked and hardlocked. Opposing freight equipment must be retracted.
3. Using the canonical indexed exit queues a **real, receipted 20/180/300-second world job**. The two pressure-rated interfaces remain sealed during the mechanical carriage cycle. The person stays in their origin room until completion; repeated use of the original request ID does not create another journey.
4. Each finite clock advance checks real equipment condition, pressure quality and differential (at most 2 kPa), rotary phase/hardlock, fixed hatch closure and electrical availability. Failed or isolated equipment, loss of power, wrong geometry or hazardous air suspends further progress without changing the character's location. Already elapsed valid work is retained.
5. After the full rated time, a physically present, capable crew member is moved into the actual destination and a separate immutable world completion event records the move and original request. A staged character is prohibited from issuing other physical machinery commands or opening another exit. If a world operator has independently removed the traveller, the old job is aborted and auditable rather than teleporting the traveller back.
6. The rotor remains captured after a successful delivery and requires a separate explicit `passenger_retract` before spin-up or freight capture. Fixed-side pressure hatches cannot be opened while the moving-frame indexer is captured or an occupant is transferring.

A local `oxplantread personnel` readout reports only the caller's nearby carriage, fixed-hatch state, current job and actual remaining time. The readout does not reveal other ship compartments.

## Important limits

- Habitation A/B share the current conservative HAB rotary capture flag; the installed two-carrier geometry is not yet modelled as two independently powered simultaneous transfer drives. No fictitious ability to transfer personnel while HAB spins is claimed.
- The coarse game simulation requires a stopped, braked, hardlocked rotor. Differential-speed moving rendezvous, person-carrying acceleration profiles, detailed seal volumes, pressure-purge cycles and the moving-carriage mechanical swept envelope are outside this bounded implementation. The independent v0.5 CAD/hub engineering package remains a *trial candidate*, not gameplay state.
- Crew health, suit operation, cabin living needs, EVA, unclassified vacuum spaces and whole-ship 40-character autonomous behaviour are separate. **No 40-crew voyage** has been performed or requested here.
- Existing 421 spaces, 517 physical access identities, 133 pressure cells, installed machinery IDs and actual inventory/ship mass remain unchanged.

## Verification

`.github/workflows/ox-g19-indexed-personnel.yml` compiles the actual movement and physical-world source, runs pure transfer/carriage safety checks and installed Evennia movement, pressure-hatch, interruption, replay and G19 compatibility tests. **Acceptance:** [GitHub Actions run #40309694557](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40309694557) passed all three jobs (**40/40 tests**): 5 pure transfer transitions, 6 installed Evennia transfers/interlocks, and 29 existing movement and cargo compatibility regressions. Tested runtime commit: `7c210fd0`. Subsequent branch changes through `43ff19a1` are documentation and command-help updates, not alterations to the tested transfer physics.

This acceptance applies **only to parked, indexed and hardlocked passenger transfer**, including all nine rated connections. It does not imply that moving HAB rotation boarding, EVA or all-room crew traversal is complete. PR #138 remains draft and unmerged.
