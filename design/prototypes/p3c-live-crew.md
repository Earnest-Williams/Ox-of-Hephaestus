# P3c - Three real authenticated crew: coolant fault and watch handover

This integration composes P2 recipient-scoped events and genuine GOAP
with the P3a independent authenticated WebSocket clients and P3b durable
physical action receipts. Three separate, nonprivileged accounts each
puppet one persistent Evennia NPC.

Lin alone gets the bridge alarm. Lin radios Ari, who physically inspects
P-01 and uses the zero-inference GOAP planner for isolation and repair.
Iona receives a request only after repair and must independently inspect
the local pump before she can authorize commissioning. Ari must inspect
the commissioned pump and verify normal pressure before reporting closure.
The authoritative world then advances the deterministic test watch clock
to 07:55. Ari offers handover and Iona accepts, transferring actual
game-side duty authority.

The game persists recipient-specific private events and only delivers
those addressed to a given character. Client input and character speech
do not mutate pump state directly. All equipment effects and interlocks
belong to Evennia and are independently verified using its database.

Limitations: deterministic authored role policies, not general-language
social autonomy or three Concordia deliberations; an explicit scripted
world-clock advance for this test, not continuous background simulation.
A further fault after Iona takes watch needs richer active-watch handling.
A passing full-server CI run establishes only this authored three-crew
cooperation and its negative tests, not general NPC intelligence.
