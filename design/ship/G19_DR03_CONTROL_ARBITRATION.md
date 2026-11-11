# Drum-3 first local takeover and remote actuation

**Scope:** only original `ISO-DR-03-LT-IF`; no general remote-flagged isolator access.

The operator commissions an additional world-owned control state only after the gateway, core network and original local console exist. The authenticated bodiless lead-mind account uses `oxdr3remote <request-id> <open|closed>`, requiring verified mixed-generation register mapping and current network connectivity. A qualified crew member physically at `LCS-DR-03` in `BE-05-SVC` uses `oxdr3local <request-id> takeover|handback|open|closed`. Crew possession wins and remains available over the original locally powered electrical panel after loss of A/B fibre.

Actual valve state remains the canonical installed isolator; neither channel creates shadow coolant state. Both use the same damaged/tripped/maintenance barriers, the one physics-clock transaction lock, immutable canonical events, and globally unique `WorkReceipt` IDs. Failed remote commands under local possession receive a durable `refused_local_priority` receipt; exact retries replay the receipt. The current mixed-generation gateway's generic remote-control flag remains false: this is an explicitly commissioned **single-point** authority, not an accidental global permission.
