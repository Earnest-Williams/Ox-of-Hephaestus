# G19 — remaining 63 cargo, portal and shield spaces

**Scope:** as-fitted v0.5, original draft G19 integration PR #138. Target is a credible working fictional freighter, not spacecraft fabrication approval.

## Existing ship inventory

- **48 cargo sectors:** eight separately manifest-dependent sectors within each of DR-01 to DR-06; 48 original rated cargo-service doors and 48 independently rated freight-handling routes.
- **12 commercial cargo portals:** P1 and P2 per drum, each with its originally fitted inner cargo portal.
- **3 shield/trim volumes:** BOW-SHIELD-FOREPEAK (penetrated nonbreathable structural shield; rated service hatch), WATER-SHIELD-FWD (sealed annular water/radiation tank; rated service hatch and original gas bank valve), WR-TRIM-TANK-BAY (closed rotating trim reservoir with no original personnel hatch).

That is **63 original unclassified space records and 110 original rated interfaces**. This implementation does not add pressure cells, body space, air, water, spare inventory, doors or a magically walkable cargo route.

## Cargo-sector access and atmosphere

The rotating gallery remains an independently enclosed crew pressure cell; a cargo sector beyond its door is NOT assumed breathable. The first operator survey discovers the pre-existing sealed gas inventory, measured free volume, pressure, temperature, oxygen, carbon dioxide and smoke of each sector. A later measurement must reconcile to that original charge minus actual mass loss, not re-create or refill air.

Each drum's eight sectors must be individually sampled and account for **all currently stowed real manifest lots exactly once**. Classification distinguishes empty, ordinary cargo, inert, hazardous and separately pressured freight. A manifest signature becomes stale if a real lot changes identity, weight, location, restraint or position. A sector clearance is not transferable between compartments.

Ordinary human access is authorised only for positively sampled safe, empty or ordinary-cargo sectors with fresh complete manifests, breathing-safe rotating-gallery gas, less than 2 kPa pressure differential, the original sound rated door, actual stationary/braked/hardlocked rotor and individual signed maintenance permit. Real Evennia exit traversal records each entry. Cargo freight-handling routes are strictly machinery, never crew passage. Hazardous, toxic, unmeasured, damaged or differentially pressured sectors remain shut.

A living worker holding a sector permit blocks that drum's new movement, cargo and port operations, as well as operator rewrites of its verified manifest. Emergency coast and safe isolation are not blocked by normal work permits.

## Commercial loading sleeves

Docking alone does NOT establish safe cargo loading. An independently approved original portal requires the exact currently connected berth, closed original sound pressure door, original healthy radial freight handler, stopped hardlocked drum and no work crew or physical leak in any of that drum's sectors. The certificate records the original door revision; a real repair or operation that changes the door invalidates certification. Undocking cancels the current certificate. A berth change needs renewed inspection.

Bulk loading/unloading and sealed waste offloading share these physical portal gates, powered transfer equipment and finite custody. Abort/recovery remains an actual time-consuming reverse operation, not a deletion of partially transferred mass. The external sleeve is **not** a human passage or an inferred breathing-safe port connection.

## Shield/trim geometry and remote controls

- BOW-SHIELD-FOREPEAK: the shield, ionizer and field coils are original equipment inside a penetrated **nonbreathable** forepeak. Inspection is at TRUNK-B-BOW control, never by fictional walk-through of solid shielding.
- WATER-SHIELD-FWD: annular nonhabitable tank, existing GAS-REFILL-BANK-A and its existing ISO-GAS-BANK-A valve. Actual local WATER-FWD instrumentation can operate that originally specified remotely operable isolator. A remote inspection requires valve shut and sound equipment.
- WR-TRIM-TANK-BAY: fixed inventory of workshop trim water, not extra ship liquid mass. It has **no** original human doorway; remote inspection requires the existing WR-01 rotor stopped, braked and hardlocked at WR-ROTOR-MACHINERY.

An authenticated shield_trim crew inspection reads real fitted condition and time but does not fabricate a new hatch, enter unbreathable solid/tank volume, repair distant equipment instantly or increase available gas/water. Major structural restoration needs an original external maintenance route or a separately designed physical intervention.

## Damage-control closure

A positively observed cargo-sector breach draws gas from its own original surveyed charge with proportionate O2/CO2/smoke loss into the ship's authoritative lost-to-space register. It cannot vent from an adjacent known crew pressure cell by inference. A damaged sector commands its individual cargo drum to coast down by **inertial physics**. It prevents conflicting freight and commercial/waste port restart.

Only a minor, still safely accessible inner breach (at most 0.05 kg/s) can receive an internal material patch: one real physically present suited engineer, genuine EVA oxygen, commissioned toolkit, 2 kg finite carried spares, original closed hatch and 180 seconds of continuously verified work. On successful completion the actual 2 kg transfers into the fitted repair account and the leak stops; the lost gas remains missing. A large or unsafe breach has no internal magic repair.

## Emergency return and unfinished internal damage control

The rated cargo-sector personnel hatch connects the compartment and its
**own co-rotating gallery**. It is not a moving-frame docking indexer.
Admission is conservative: each of the eight sectors needs a fresh,
complete verified manifest; the drum must be stationary and hardlocked;
the destination gas and gallery must be breathing-safe and matched within
2 kPa, and a living named crew member must hold the permit.

After admission the operator cannot resurvey an occupied sector. A later
ten-minute survey expiry, a bearing casualty that starts an inertial coast,
or a lost manifest verification therefore cannot by themselves bar the
**already inside permit holder** from returning to that same co-rotating
gallery. If the rated hatch is CLOSED, opening it still requires verified
safe, pressure-matched air and refuses a large uncontrolled leak. But if
a casualty happens after the actual sound hatch has ALREADY opened, an
ambulatory authenticated owner can travel its original reverse Evennia
exit even during dangerous decompression. That exception never opens a
hatch, admits new workers, defeats a failed door, re-arms machinery,
or teleports an incapacitated person; casualties need a real rescue
procedure.

If a minor leak seal is interrupted, the work does not continue with an
absent or endangered technician. The holder may return to the gallery
through the original safe access, close the rated hatch, and use
`cargo_sector ... abort_seal` before releasing the now-empty worksite.
The unsolved leak rate and all previously lost gas remain unchanged, and
no 2 kg replacement stock is debited. A different person, an open hatch
or remaining crew inside cannot cancel another worker's incomplete job.

The acceptance matrix now includes an all-48 gas conservation sweep,
independent revision-bound verification of all 12 commercial portals,
real crew breathing and long-duration egress, and finite-material
interrupted-patch tests. CI exposed two previously incorrect acceptance
fixtures: a cargo manifest cannot start with zero original onboard mass;
and an already fully loaded ship cannot accept another 1,000 kg simply
because a loading sleeve passed pressure inspection. The latter case is
now explicitly checked as an overload rejection, followed by a legitimate
outbound transfer of 3,000 kg already in the ship's reference freight.
Both corrections preserve actual onboard mass and existing port interlocks.

The original 63-space revision passed its three focused jobs at
[run #40804699570](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40804699570).
The latest compound-casualty runtime `f0221bbd` also passed all three
jobs at [run #40876903140](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40876903140).

## Acceptance and integration boundaries

The focused three-job GitHub Actions workflow is .github/workflows/ox-g19-unclassified.yml. It covers pure 48/12/3 source identities and conservation, installed Evennia cargo manifest and original doors, real portal berth and transfer operations, the three non-personnel voids, and existing freight/industrial compatibility. Mark the new phase accepted only if all three jobs pass on the actual latest runtime commit.

The 40-crew voyage remains excluded and PR #138 remains draft/unmerged. Existing G19 whole-ship cross-casualty acceptance is a separate closure gate.


## Coupled open-hatch casualty, actual retreat and pressure accounting (29 October 2026)

A physically observed sector hull breach can now begin while the original
rated personnel door is OPEN or already broken. The clock cannot make an
observed breach vanish because the hatch is not closed. Soundness still
governs crew entry and actuation, but a failed OPEN hatch passes physical
gas, oxygen, carbon dioxide, smoke and heat through its original gallery
boundary and never halts the whole physics clock.

Every ten-second substep now exchanges finite, surveyed sector/gallery gas
and subsequently debits the same substep's real shell leak. A persistent
`gallery_net_kg` account, upgraded from older v1 sealed inventories,
conserves original measured mass without creating any of the 133 commissioned
normal pressure cells or gas reserves. A fully vented known sector (0 kg)
still accepts bounded finite air through an open door without division by zero
or frozen ticks. Once the rated door shuts, its sector loss persists but
the independent gallery debit stops. The actual rotating machinery coasts
down and cannot restart during a sector breach.

Installed tests prove (1) shell casualty with an open rated boundary and
gallery pressure loss, (2) isolation, continued loss and blocked motor
restart, (3) living owner egress through the physically open real exit,
(4) impossible bypass of a shut or failed door, (5) continued simulation
with a broken-open hatch, and (6) a three-real-person timed casualty
transfer from DR-01-GALLERY to DR-01-HUB with actual original passage,
an authenticated qualified leader and helper, and no simulated 40-crew trip.
The patient's independently evidenced impact injury is an explicit test
fixture, not a claim that decompression automatically caused that injury.

The **three-job pure / installed / compatibility acceptance passed** on
runtime `f0221bbd`:
[focused CI #40876903140](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40876903140).
The workflow now adds an independently isolated **adjacent_acceptance**
job covering existing EVA/major hull containment, actual two-carrier rescue,
finite hull patch, commercial movement and medical work-pausing. This expanded
cross-system check must pass on its new workflow head before calling the
wider casualty slice accepted.

G19 remains an unmerged draft integration PR. Full-vessel G19 acceptance
remains separate; the 40-crew voyage remains excluded.
