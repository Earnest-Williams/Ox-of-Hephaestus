# Ox of Hephaestus — current roadmap

**Baseline: 30 October 2026.** Full-ship G19 engineering is **accepted and merged** ([PR #138](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/138)), with [post-merge fuzz correction](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/139) also merged. This page proposes what to build next; listed future work is not already implemented or approved for production.

The superseded long-form G1–G16 plan and 25 October G18b work-in-progress notes are preserved in the [archived roadmap](archive/ROADMAP_PRE_G19_2026-10-25.md). For what is actually merged use [STATUS](STATUS.md); for physical acceptance use the [G19 record](ship/G19_ACCEPTANCE_RECORD_2026-10-29.md).

## Accepted baseline

- **Ship:** 421 rooms, 517 authored links, 133 pressure cells and 808 equipment units in 91 families, installed under a single Evennia authority.
- **Integrated functions:** electricity, atmospheric control, thermal, fire, equipment, hull, water/waste, cargo/mechanics, propulsion, exposure, access and recovery.
- **G19 verification:** final multi-system acceptance 74/74 tests plus three independent process-restart phases, 47/47 final-head workflows and 28/28 main-branch G19 acceptance checks reported at merge.
- **Crew:** independent Concordia/GOAP minds and real authenticated character actions currently operate a separate seven-compartment proving ground, not the full ship.

## Priority 1: harden post-merge physics — done

The [G19 fuzzing](ship/G19_FUZZ_CAMPAIGN_2026-10-30.md) findings are closed: F5-1 and F6-1 to F6-3 in [PR #141](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/141), and the residuals from its rerun in [PR #144](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/144). The F6 sweep now ends with 0 crashes and 3 persisted mutations, all legitimate states. Keep the seeded fuzz and persisted-safety regressions running in CI.

## Priority 2: move autonomous crew onto the actual ship

1. Extend the world-advertised **actor-local capability graph** and handler GOAP traversal to G19 exits, under real pressure, suit, indexed transfer, EVA and permit rules.
2. Stage specialist duties and crew migration while preserving durable identity, belief/evidence histories, pending work and exact request IDs.
3. Observe actual equipment diagnostics and incident reports; send characters to instruments, stores and real workstations.
4. Perform power isolation, casualty control, finite repair, verification and restart with ordinary character commands. Reconcile receipts and observe real physical output.
5. Test cooperation, inaccessible routes, missing tools, depleted supplies, interrupted work, multi-process restart and contradictory observations.

Do not invent an alternative physics state in the AI handler. Treat canned GOAP scenario success as bounded evidence only.

## Later distinct milestones

- Shipboard employment, freight contracts, port and cargo economy, staffing and sustained operational gameplay.
- Graded skill-sensitive practical attempts, acquired conditions, broader study and character development.
- Optional deferred engineering devices (routine inert makeup/leakage, cabin emergency banks, generator-enclosure fire suppression, navigation hazards): each needs a play-facing requirement and new acceptance scope. The [G19 deferred list](ship/G19_ACCEPTANCE_RECORD_2026-10-29.md) is the source.
- The human joined-world/handler observatory, after it has a concrete use. The present spatial terminal is a read-only development tool.

## Release discipline

For each change, identify the state owner, authoritative schema, permissions, resource limits, failure conditions, restart semantics and evidence. Run relevant real Evennia, collision/concurrency and selected PostgreSQL CI. Keep [STATUS](STATUS.md) and the operating guides current in the same PR.

Historical original: [pre-G19 roadmap](archive/ROADMAP_PRE_G19_2026-10-25.md) · [early architecture](archive/ARCHITECTURE_THROUGH_2026-10-21.md) · [prototype research](prototypes/README.md).
