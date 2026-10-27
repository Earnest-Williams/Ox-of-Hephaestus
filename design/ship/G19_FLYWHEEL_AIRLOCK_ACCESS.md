# G19 — original F1/F2 sealed flywheel service airlocks

The original ship has two **already authored** `service_airlock` connections:
`ACC-F1-BAY` from `TRUNK-A-F1` into `F1-BAY`, and `ACC-F2-BAY` from
`TRUNK-A-F2` into `F2-BAY`. Both are fixed-frame, pressure-rated, normally
sealed connections. Both bays retain **unsurveyed unpressurised** atmosphere
rather than being falsely commissioned as new breathable rooms.

This subsystem models each as a captive two-seal transfer mechanism. Gas
contained in the original airlock assembly is lumped into its original trunk
pressure-cell inventory; cycling retains/retrieves it in the same sealed
assembly, and neither exterior/bay gas nor invented oxygen is delivered to
the trunk. The original service hatch remains positively CLOSED to normal
corridor traversals throughout the 180-second cycle; the special movement
machine delivers the worker only at completion. Only one crew member per bay
airlock may cycle at once, and the two independent bays can be used concurrently.

An operator commissions both as-built devices with
`commission_g19_flywheel_access(operator_approved=True)` after commissioning
the original fitted EVA plant. Individual bay attestations are explicit:
`survey_g19_flywheel_access(bay_id="F1-BAY", operator_approved=True)` and
the corresponding F2 survey. This claims service-rating, NOT safe unsuited air.

The engineer must be an actual, registered living Evennia character wearing
one **existing physically issued EVA suit** with sound integrity and enough
finite oxygen for the transfer plus reserve. The adjoining `PZ-TRUNK-A`
pressure cell must have genuinely breathable conditions; the as-built local
panel, hatch and pressure-rated geometry must be intact. Ordinary unknown-gas
doors, freight gates and rotary collars cannot borrow this authorisation.

Entering and leaving use the corresponding original Evennia directional
`ACC-F1-BAY` or `ACC-F2-BAY` exit. A successful preflight queues a
180-second time-bound, replay-safe request. The ship's existing clock
suspends the work on hatch damage, loss of sound suit/life support or
unsafe trunk gas; it moves the real body at completion and journals the
physical transfer. The suit remains the sole respiratory source inside
the unsurveyed flywheel worksite; no gas is generated for it.

This opens physical access to the two fitted flywheel bays. It **does not**
make individual high-energy flywheel service safe without subsequent
electrical disconnection and repair-site permissions. The service-airlock
cycle is deliberately coarsely lumped rather than CFD or an independent
volume simulation, consistent with the game's existing machinery level.

Acceptance tests: `ox-g19-hazardous-access.yml`, which runs bounded pure
state-machine tests plus real installed suit/airlock/return regressions.
