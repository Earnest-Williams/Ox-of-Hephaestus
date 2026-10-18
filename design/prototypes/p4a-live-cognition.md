# P4a — Three native Concordia entities on the real ship (PR #13)

P3c proved an authored, model-free three-client cooling incident. P4a
instantiates **three separate native Concordia entities** with independent
identity, private observations, memories, revisions and persisted snapshots,
then uses them to make **bounded choices** in that same real Evennia world.
The handler connects as three non-privileged clients; it never reads
Evennia's database or invents a physical outcome.

Routine isolate/repair/commission procedures remain GOAP-driven and require
Evennia's authoritative physical receipt. The chief must physically inspect,
approve and hand over through normal commands. An entity may choose *defer*;
this safely stops the bounded demo, rather than automatically falling back
to a scripted action. The deterministic Concordia MockModel used by CI picks
the first offered action; CI establishes integration and authority, **not
emergent reasoning**. An opt-in Gemini evaluation sets
OX_COGNITION_PROVIDER=gemini and GEMINI_API_KEY (no key in CI); model
refusals or insufficient inference are explicitly not retried as effects.

Decisions prompted by received events are not synonymous with outcomes.
The model is never given the other crew member's memory. Actions without
an actor-visible durable receipt remain unknown; later stages must add
acknowledgements for social actions, not silently treat text as proof.

P4b introduces an independently running supervisor and a real world-clock
scheduler, multiple incidents and handler crash recovery. The browser
observatory remains intentionally postponed.
