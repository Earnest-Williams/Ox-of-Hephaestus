# Atmosphere-casualty reference — v0.5

**23 October 2026 · selected physical candidate only.** This quantitative screen does not operate valves, prove repair, spend live inventory or decide that a compartment is safe to enter.

`check_atmosphere_casualties.py` independently computes one-arc and two-arc worst-case reference loss against the existing two 2.75 t gas reserves, using the 133-cell bounded gas ledger. The example is an evacuated HAB-03 reference cell (about 3.088–3.705 t gas at 101.325 kPa and 20 °C). Two intact banks nominally cover a single total arc loss; one bank cannot. Both intact banks cannot cover **two** such fully evacuated arcs. With 200 kg/h combined reference throughput, replacing HAB-03's entire planned reference gas requires at least **15.44–18.53 hours**, before ramping, thermal limits, contamination checks or restoration of the leak.

The permission flag in this *diagnostic* requires all three independently asserted preconditions: a real gas-route verification, repair/isolation of the leak, and verified receiver conditions. Any missing condition blocks the estimate's refill-start flag and all represented nominal reserve consumption. This is deliberately distinct from future world-authoritative state, which must prove each condition from live observations, tools, valves, tickets and measured gas. The example never pretends the model's nominal lower/upper gas masses are installed measurements.

Ten invalid-casualty screens cover lost fractions beyond 0–1, NaN, duplicate or nonexistent bank stock, excess/zero gas flow, fabricated authorisation, missing pressure cells and falsely measured installed air. Full-ship movement, cargo-sector containments, and the 131 rated unknown-receiver thresholds remain governed by their separate validators.

No additional gas bottles, pressure cells, inventory, equipment or route IDs are created by this reference. The script is stdlib-only and runs in the ship-design CI workflow.
