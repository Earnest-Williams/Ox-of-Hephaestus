# G19 — crew breathing and persistent environmental exposure

**Status:** WIP on draft PR #138. Standalone and installed-ship acceptance pending. This is ordinary game-world crew physiology, not a medical diagnosis system and not astronaut certification. **Do not run the deferred 40-crew voyage.**

## Authority and enrolled characters

The ship already has 133 installed pressure cells, actual atmospheric circulation, water and filters, finite suits, independently fitted EVA locks, and real Evennia character locations. The exposure transition kernel existed as `ship_crew_exposure.py` but was not connected to ordinary characters. The new `ship_crew_physiology.py` is a pure bridge between that kernel and the existing gas cell and temperature/energy ledger. The Evennia engine remains the authority for time, crew position and individual durable condition.

An operator explicitly calls `commission_g19_crew_physiology(actor_dbrefs=[...], operator_approved=True)`. The actor must exist, have a crew identity and physically occupy a canonical ship space. The system creates one persistent `crew_health:#id` row **per named real character**, not a simulated anonymous complement. Repeated enrolment cannot reset injury, hypoxia or thirst; invalid or duplicate actor IDs are refused. The separate water-treatment model's nominal planning complement does not constitute a 40-character gameplay voyage.

The authoritative world advances every enrolled character only when the G18/G19 bounded ship clock advances. It samples the character's actual pressure zone, not a requested or assumed destination. On each 10-second integration slice, the measured gas pressure, oxygen and CO2 fractions, smoke loading and temperature influence that person's condition. Unknown atmosphere is not substituted with breathable air, and an unsuited character moved into actual external vacuum accumulates injury.

## Finite atmosphere and suits

An unsuited, living person consumes approximately `0.00001 kg/s` of oxygen in this gameplay abstraction. The cell loses that exact oxygen mass and gains the same mass as CO2: a consciously simplified mass-conserving respiratory proxy until a detailed food-carbon ledger exists. It neither creates atmospheric mass nor provides a free oxygen tank. The worker's ~80 W resting metabolic heat enters the *same cell's finite thermal store*. Smoke, overheating, hypoxia and water deficit accumulate in the person's durable condition; a return to healthy air can reduce immediate hypoxia, but does not instantly erase injury.

Issued EVA suits are different: `ship_eva_operations.py` already charges and consumes strictly finite oxygen from physically issued damage-control stores. A suited character breathes from the **one real suit** and is not charged a second time to the room atmosphere. The suit's respirator accumulates CO2 and eventually becomes unfit without servicing. Every new wearer inherits **their own chronic condition**, not the previous wearer's injury; existing residual suit oxygen and CO2 are physical equipment stock and are never magically reset by changing wearer.

Incapacity, critical injury and terminal casualties block physical crew traversal. The same character condition is available to damage-control and repair work rather than an AI-owned narrative value. `oxplantread crew` returns only the caller's own measured physical condition and place, not a ship-wide medical oracle.

## Acceptance boundaries

The implementation does not yet claim calibrated medical prognosis, automatic treatment in HAB-04, finite medicinal consumables, recovery transport, nutrition/sleep systems, or all-crew voyage endurance. The ship **does** have authored HAB-04 treatment, observation and isolation rooms and a pharmacy/stores; future recovery should be attached there with real equipment and material custody, not an instantaneous global cure.

Tests are in `world.tests.test_ship_crew_physiology` and `world.tests.test_installed_ship_crew_physiology`; the dedicated `ox-g19-crew-physiology.yml` runs these alongside the existing exposure and EVA kernel. The installed suite enrolls only two actual Evennia actors, verifies their shared gas accounting, exposes a worker to a real leaking EVA pressure cell, checks the suit avoids double breathing, and proves a repeated game-time tick cannot consume additional gas. **Acceptance requires passing CI and adjacent G18/G19 compatibility.**
