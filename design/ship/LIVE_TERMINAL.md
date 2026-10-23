# Live ship terminal — first working UI slice

**Branch:** `integrate-ox-ship-world`  
**Source geometry:** `design/ship/Ox_Ship_Wire_Render_v0.4.html`  
**World authority:** persisted Evennia `ox_ship_world` rooms  
**Status:** spatial telemetry only; operations remain in the existing prototype until migrated.

## What runs

The existing single-file Canvas wire renderer is still the visual foundation.
There is no duplicate 3D scene graph and no browser recreation of Evennia's
physical world. The authenticated terminal view serves the original HTML and
injects two small separate assets:

- `game/web/ox_terminal.css`: industrial shipboard-terminal treatment;
- `game/web/ox_terminal.js`: read-only room-state overlay, selection and fault markers.

The original standalone render remains usable unchanged outside Evennia.
Geometry and authored equipment/service diagrams come from the embedded
`ox_full_ship.json`. Conditions shown as **world state** come exclusively from
Evennia's tagged, persistent canonical rooms, not from that embedded JSON.

## Routes

| URL | Function | Access |
| --- | --- | --- |
| `/ox/console/` | ship wire/telemetry terminal | Authenticated Developer |
| `/ox/console/theme.css` | terminal treatment | Authenticated Developer |
| `/ox/console/live.js` | browser-side overlay | Authenticated Developer |
| `/ox/api/v1/spatial-state/` | bounded, read-only JSON snapshot | Authenticated Developer |

Anonymous requests receive HTTP 401; authenticated non-Developers receive
HTTP 403. No mutation endpoints are added. No cross-origin or public asset
publication is required. Requests use the existing same-origin Django session
cookie and remain local-only under current game settings.

The terminal reads the source file from `design/ship` on the server; deploying
the game must retain that file and the model JSON alongside the game directory.
**Model/render version gate:** the server currently registers only the verified
v0.4 wire HTML for the canonical v0.4 model. If the model later advances to
v0.5-candidate or v0.5 without a matching generated, reviewed and explicitly
registered wire renderer, `/ox/console/` returns **HTTP 409** before serving
a mismatched scene; a missing registered file returns **503**. The JavaScript
model-version equality check remains an additional independent safeguard.

## Runtime projection

`world.ship_telemetry.read_spatial_telemetry()` selects only the canonical
space-tagged Evennia objects and exports exactly:

- `ox_space_id`;
- `ox_current_condition`.

It also includes the materialised-space count, expected count, model version
and whether the topology is complete. Evennia attributes are pre-fetched in
bulk to avoid individual ORM queries for each of the 421 spaces.

It **does not expose** AI memory, crew whereabouts, private interpretation,
character profiles, inventory, incident receipts, raw object attributes or
unmigrated equipment state. The JSON source's equipment objects may still
appear in the background *drawing*, but are labelled source data, not live
machinery.

Example response, abridged:

```json
{
  "schema": "ox.telemetry.spatial/0.1",
  "model_version": "0.4",
  "topology_complete": true,
  "scope": "developer_spatial_only",
  "coverage": {
    "spaces_expected": 421,
    "spaces_reporting": 421,
    "equipment": "not_integrated",
    "service_networks": "not_integrated",
    "crew": "not_exported"
  },
  "space_states": [
    {"id": "CMD-PRIMARY", "condition": "serviceable"}
  ]
}
```

## Browser behaviour

The terminal polls every eight seconds while the page is visible; manual
refresh is also available. This is deliberately **not** yet a WebSocket
subscription or an alarm/event stream. A disconnected feed is marked stale
rather than silently treating a last-known condition as current. A world/model
version mismatch fails closed rather than drawing world conditions over the
wrong geometry. The v0.5 design candidate retains all 421 identifiers and 517
physical connections, but its equipment inventories and pressure engineering
are different; topology identity **does not** make v0.4 geometry/fit-out
automatically an acceptable v0.5 graphical source.

The original room inspector is left operational, with its `Condition` field
relabeled `Source condition`. A separate `World condition` field appears
for materialised rooms. Any exceptional condition is drawn as an amber or
red diamond. Selecting its alert entry focuses the existing wireframe camera
on the relevant room.

The palette borrows from late-1970s/1980s industrial terminal aesthetics:
restrained phosphor green, amber system titles, red casualties, technical
typography and subtle scanlines. It should read as a practical industrial
instrument rather than as a graphical videogame HUD.

## Local development

Start the existing Evennia game with its local settings and log into the
website as a Developer, then visit:

`http://127.0.0.1:4001/ox/console/`

The browser itself does not directly query Django's ORM. All state crosses the
explicit read-only server projection. If the main world has not completed
initialisation, the display reports incomplete installation and does not
fabricate normal system health.

## Verification and next expansion

The existing `ox-departments` CI workflow now checks JS syntax and exercises
terminal authorisation, response boundaries, live state updates and stage-one
ship-world regressions under real Evennia tests.

Next steps:

1. Graduate the spatial-state feed to a revisioned, authenticated event stream
   when world-owned state change events and reconnect semantics are available.
2. Materialise the first critical equipment objects and telemetry bindings.
   The bridge, Engineering Control and hab refuge systems are natural first
   targets.
3. Add sensor provenance, freshness, failures and visibility policy. A broken
   sensor must not reveal unobservable ground truth to a regular crew console.
4. Render pressure boundaries and door/interlock states once those actions
   exist in Evennia, instead of using static JSON `normal_state`.
5. Expose a separate crew-facing view with role-limited observation, leaving
   this Developer display an explicitly privileged diagnostic tool.
