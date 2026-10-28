# G19 — F1/F2 flywheel maintenance lockout

The installed v0.5 ship carries 64 individually-isolatable F1/F2 energy-storage modules, 32 in each vacuum bay. Each has a real breaker, motor-generator and a separately surveyed electrical charge in kWh. The bank switchboards have their own A/B incoming contacts. This subsystem combines the **accepted original suited F1/F2 airlocks** with the existing six reusable repair toolkits, finite carried spares, measured oxygen/CO2 suits, crew physiology, energy sources and repair work orders.

An OPEN breaker does **not** imply a stopped flywheel. A module service permit requires an individual surveyed energy store at measured zero kWh, mode \`standby\`, healthy OPEN module breaker, rated vacuum-bay worksite and a physically present, qualified person wearing a *real issued suit*. The legacy \`ox_suit_verified\` actor boolean does not grant F1/F2 access.

Commission normal G19 electricity, water/materials, repair custody, EVA and F1/F2 bay airlocks first; survey both original vacuum worksite/access locations. Then call \`commission_g19_flywheel_service(operator_approved=True)\`. This neither fills stores nor clears old damage.

Commands:
- \`oxplant <request-id> flywheel_service F1-FW-01 lock\` — issue individually owned persistent lockout after actual isolation
- \`oxplant <request-id> repair equipment:F1-FW-01 start\` — requires measured permit, damaged original module, personally carried spares and reusable toolkit
- \`oxplant <request-id> flywheel_service F1-FW-01 release\` — only its original issuer after finishing real work
- \`oxplantread flywheel_service\` — local charge, actual breaker, permit and work order, restricted to attended bay

A full failed-module repair installs 3 kg of **previously issued** spares and consumes 600 seconds of physically staffed game time, with ordinary sickness, suit exhaustion, tool custody and breaker faults able to pause progress. Completion restores machinery condition, **not** flywheel charge or commanded operation. Lockout remains until explicit release and blocks module re-connection or charge/discharge commands. Other isolated flywheel modules can still operate via their own feeders. Repairing the *bank switchboard* instead requires the two infeed breakers and all 32 module feeder contacts physically OPEN. No instant rotor spin-down or imaginary vacuum air is introduced.

The subsystem is not a detailed contact/bearing FEA. The prohibited 40-crew voyage is excluded. Dedicated CI is \`ox-g19-flywheel-maintenance.yml\`; the existing installed electrical tests now require actual issued suits rather than legacy attestations.
