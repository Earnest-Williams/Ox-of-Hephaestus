# G3c — Teo / Mara cooperative supply with epistemic separation

**Status: tested and merged** in [PR #40](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/40): all 37 CI jobs across 23 applicable workflows passed on the final code commit. The world-inventory foundation and epistemic boundary were merged in PRs #39 and #38 respectively.

The initial G3 vertical slice is a five-crew, restart-safe dependency:
Teo needs an A-01 cartridge; Mara can deliver one from Cargo Hold;
Teo resumes only after the world validates the delivery. Every action
uses an ordinary authenticated Evennia character session and a global
durable WorkReceipt; the model never directly edits stock or orders.

## Distinct minds, not a distributed omniscient narrator

1. Teo *observes* zero local cartridge stock at A-01 and the world
   refuses a replacement. That fact is local and time-stamped; Teo
   knows his own shortage, explicitly *does not know* cargo reserve,
   and can *believe* help is possible without pretending it is true.
2. Teo chooses request_supply. Only Evennia can create the matching
   SupplyOrder, attached to the real Teo character and assigned to
   the posted cargo officer. A request **does not create stock**.
3. Mara cannot use the supervisor's shared work-step record as a
   source of character knowledge. Mara must first observe the real
   supply_request event in **Mara's own inbox**. Acceptance indicates
   willingness, not certainty of available cargo.
4. Mara physically attends Cargo Hold using the private, locally
   learned GOAP map, then uses oxinventory to read available stock.
   Remote Teo stock is not visible; zero can only be asserted after
   Mara's own authenticated local world reading.
5. A genuine collect_supply receipt moves ONE serialized item into
   Mara's physical carrier identity, visible in her own inventory.
   A fresh inventory reading confirms she still carries that serial
   before any new delivery attempt.
6. Mara navigates normal room exits to Environmental Plant, then
   performs deliver_supply. The game moves the SAME item into
   environmental storage, records a durable world receipt, and
   separately addresses the delivery event to Teo.
7. Teo must receive the correctly addressed supply_replenished
   event AND freshly observe the real available quantity in the
   environmental compartment. Only then does Teo reconsider his
   blocked agenda, submit a new replacement request after the
   permanently failed old one, and consume the real delivered
   cartridge. A-01's world-owned state machine validates all steps.
   The ledger retains a separate historical scrubber.verified_delivery
   fact identifying the observed item serial, distinct from the changing
   current scrubber.spares count. Consuming a cartridge must not erase
   the evidence that the delivery actually occurred.

## Faults and persistence

WorkStepLedger persists a stable ID before submitting each step.
Lost ACK after the world commits delivery does not cause a
duplicate item, second order, second delivery or second cartridge.
A fresh supervisor process reconciles the original pending ID
through authenticated oxworkreceipt. If the result remains
unknown, it does not mint a replacement ID.

SupplyOrder is *world owned*. The handler's own g3_supply record
is only a bounded local progress/intent tracker and is bound
to Teo and Mara's authenticated DBrefs. The two private
AgentEpistemics ledgers remain independently scoped.

The G3c real-server test runs three independent external handler
processes (request, deliberately dropped delivery ACK, final
reconciliation and maintenance) and restarts the actual game server
between delivery and reconciliation. It independently verifies
both characters' final actual locations, exact item-state
conservation, four inventory work receipts, a failed and later
successful A-01 replacement receipt, and private recipient events.

## Runtime mode

Enable this prototype's automatic supply path with:

    OX_G3_COOPERATIVE_SUPPLY=1 python -m ox_ai.runtime.five_crew_service serve

The default remains opt-in to preserve older deterministic
recovery/incident acceptance cases. The supplied stand-alone
three-step acceptance commands are:

    python -m ox_ai.runtime.supply_trial request
    python -m ox_ai.runtime.supply_trial drop-delivery-ack
    python -m ox_ai.runtime.supply_trial finish

They require a real Evennia server and five individually provisioned
ordinary accounts; these commands never create cargo stock.

## Explicit limits

The slice currently coordinates one Teo/Mara A-01 supply dependency
per supervisor. It is not a general object economy, contract market,
employer scheduler, or UI. A new cargo shipment source and additional
simultaneous work orders must extend the world's schema and scheduling
without sharing private memories. Unknown unknowns are recognized
only retrospectively as surprising verified observations, not listed
by an omniscient simulation layer.
