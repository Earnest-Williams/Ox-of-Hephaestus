# G19 — first lead-mind watch trigger

**Implementation slice:** authenticated, event-time **watch predicate** for one
already fitted and surveyed source, the passive drum-3 hatch contact at
`ACC-DR-03-LOCK-FIX`. This is the first part of the lead mind's
[watch-mode design](../interface/ship-mind.md#time) and
[operations build plan](../operations/build-plan.md).

## Physical and network authority

The existing `ACSR-DR-03-FIX` dry contact is not an actuator. It records
actual hatch transitions only when fitted and surveyed, through the
already-powered `GW-LCS-DR-03` input. The established A/B ship-network
delivery mechanism carries those observations to the enrolled, bodiless
lead-mind account **only while the network, gateway and cooled computer
remain usable**. Local contact events produced while the network is dark
never enter the player's later inbox retrospectively.

The watch relies exclusively on that account's **newly delivered**
`g19_access_network_delivered` capsules. It cannot inspect raw ship events
or private character state, advance a world tick, or actuate a hatch.

## Account commands

These are in the OOC authenticated account command set, never a
character or crew's default command set.

| Command | Result |
|---|---|
| `oxwatch <32-hex-id> open` | Arm one watch for a newly delivered drum-3 hatch transition to open |
| `oxwatch <32-hex-id> closed` | Arm the same source for a transition to closed |
| `oxwatchstatus` | Read idle, armed or fired; fired returns the delivery event ID and source time |
| `oxwatchcancel <32-hex-id>` | Cancel the armed watch and record a durable receipt |

All commands require the original operator-enrolled account and **currently
verified network access**. The global request-ID ledger deduplicates repeated
arm/cancel requests and rejects collisions across ship operations. Only one
watch may be armed at a time. A fired watch stays in the canonical world
record until the account chooses to arm the next one.

When a newly delivered, real contact transition matches, the world
records one `g19_ship_watch_fired` event citing that exact delivery.
Its source time is the observation's game time; it does **not** mean the
hatch is still in that position at status-read time. No actor identity,
inferred location, or crew state enters the watch's result.

## Failure and reconnection

- An unchanged hatch setting creates no contact transition and no watch trigger.
- A manual action during a dark or unqualified network remains local; a
  later survey and reconnection cannot replay it into a watch.
- A new, **post-reconnection** matching transition can fire an armed watch.
- Firing is one-shot, persistent, and independent of whether an account
  currently has a session open.
- Cancelling and rearming do not erase prior event history. A renewed
  watch starts after its own durable arm event, never from a raw event scan.

## Strict scope limit

This is **not yet full watch mode**. The game clock is not paused, accelerated
or advanced by these commands; a graphical "watch until" loop, pause
semantics, expiry/threshold watches, scheduled obligations, expanded
sensor coverage, and captain/crew-message triggers are later packages.
It supplies a verified, world-owned wake **condition** to build those
behaviours on, without claiming any automatic time control.

## Verification

Pure tests reject spoofed deliveries, wrong account/epoch, old sequences,
nontransitions, malformed control records and unexpected actuation/time
rights. Installed tests use real Evennia account enrollment, actual crew
hatch operations, PostgreSQL receipts, measured G19 gateway supply,
surveyed A/B fibre, and finite cooled compute. They require one-shot fire,
idempotency, genuine cancellation, account isolation, dark-network
non-delivery, fresh resurvey and post-recovery triggering.
