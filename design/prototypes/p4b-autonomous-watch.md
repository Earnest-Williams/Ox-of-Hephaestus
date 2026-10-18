# P4b — Persistent autonomous watch and world-owned game-time duties

This stage replaces the one-shot P3 test with a real long-lived service entry:

    python -m ox_ai.runtime.watch_service serve

It connects three unprivileged normal Evennia accounts, restores the
independent Concordia brains and their own observations, checks world-owned
inbox catch-up on startup, and suspends on an actual WebSocket event between
incidents instead of polling models on idle ticks. Each alarm is handled by
the engineer who holds the posted watch, as read by the bridge character
from its ordinary in-game roster. Approved GOAP operations are attempted
through receipt-bearing physical commands. The model may defer work; the
handler never replaces a refusal with a silent physical fallback.

Evennia's persistent ShipDutyClock Script owns scheduled handovers: a world
timestamp, not a model request or incident closure, fires the duty due
event, exactly once. No hard-coded clock advance is used in this stage's
live trial. The earlier P3 deterministic fixture is retained unchanged.

After Iona takes active engineering watch, the real world enforces that
only Iona can operate P-01. Ari, now off watch, becomes the explicitly
delegated *independent safety reviewer*, who must inspect personally
before approving Iona's commission. Iona cannot sign off her own work.
Role delegation, physical locality and pump transitions remain game state.

Recovery: the service writes its phase and native agent checkpoints before
submitting a physical isolation request. If the handler crashes or loses its
acknowledgment, restarting the service reconciles that exact actor-bound
receipt. It never blindly retransmits the isolation action. The acceptance
workflow executes two incidents against one persistent SQLite world, changes
the active engineer between them, stops and starts the independent handler,
then verifies the real game event ledger contains exactly one isolation per
incident and the correct reviewer approval.

The CLI's begin/resume modes deliberately test that recovery boundary in
two distinct OS processes. The serve mode repeats the same event-driven
sequence for later alarms. Idle periods do not invoke an LLM.

**Boundaries:** This is an early operational service for one pump and three
crew, not a generic scheduling service, broad language-based collaboration
or an interface. The deterministic Concordia MockModel in CI proves native
cognitive and world wiring, not generalized model reasoning. An actual
model is opt-in with OX_COGNITION_PROVIDER=gemini. The service must be
started by an operator/supervisor in an installed runtime; GitHub CI
does not deploy a permanent spaceship server. The observatory is deferred.
