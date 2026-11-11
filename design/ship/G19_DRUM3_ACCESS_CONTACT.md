# Drum 3 passive access contact — first fitted reader

**Status:** first physical access-sensor implementation; no player principal or
remote access-reader API is activated. Built on the read-only gateway support
merged in #151 and the access-event projection in #152.

## Physical position and electrical custody

- Contact at the original fixed personnel hatch `ACC-DR-03-LOCK-FIX`,
  mounted on the `DR-03-SERVICE-LOCK` side.
- Cable to `GW-LCS-DR-03` follows the original five-room A-side drum
  corridor via `TRUNK-A-DR-03`, `LOGI-STOP-DR-03` and
  `TRUNK-B-DR-03` into `BE-05-SVC`.
- The source is a *passive dry-contact input* sensed by the already metered
  50 W gateway. No separate powered sensor, unstated continuous load or
  independent heat rejection has been introduced.
- A continuity and pressure-penetration survey is mandatory. Sensor or cable
  damage invalidates the certificate. Merely refitting cannot erase faults.
- A dark gateway input or open local fuse withholds observations. Loss of
  ship-wide data rails does not stop the contact's *local* records. Remote
  delivery remains unavailable until separately authorized and receipted.

## What it actually observes

A contact closing or opening at a real crew hatch operation can be witnessed
only after installation, commissioning and a powered current feeder. Each
observation is a new **Evennia-owned** `CanonicalShipEvent` with the
original event ID, state transition and timestamp, and never copies the
operator's identity or private beliefs.

The contact does **not** report people passing through, a numerical location
estimate, a door seal's pressure integrity, or an unobserved historic hatch
operation. The existing event projection must not treat its physical event
history as authenticated network-delivered data until the reader-delivery
contract is fitted.

## Acceptance

Test the actual original 50 W supply, finite heat rejection and fixed hatch.
No observation when unfitted, unverified, or damaged; exactly one for each
measured transition after commissioning; no duplicate for a no-op or a
resaved event; no retroactive capture; no actor identity; an opened physical
fuse immediately removes observation; old events survive and re-fitting cannot
undo damage. Future work is authenticated reader delivery and local takeover.
