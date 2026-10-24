# G16m — actual 6/20/40 simultaneous Decider queue measurement

**Experimental benchmark only; never a permission to activate the
personality supervisor.** G16f measured 66 separate Concordia minds
**sequentially** using 198 genuine Decider Q4 forwards. G16i modeled
hypothetical arrivals under a fixed 25-second wall deadline. G16j
instrumented the real scheduler with queue waits, native-worker activity
and early vs late deadlines.

[G16m](../../scenarios/profiling/g16m_native_queue_burst.py) closes that
specific measurement gap by placing **6, then 20, then 40 independent
actors into the real G16c scheduler on the same event-loop turn**,
while using the genuine G15 three-position-balanced Decider 4B Q4_K_M
engine on a single shared CPU inference lane. It keeps the production
**25-second timeout**, uses the exact original model and publisher
tokenizer revisions, and verifies the full expected SHA-256 before
loading. The actor creation, tagged menu, private seed memories,
durable boundary and pre-adoption choice checkpoints are the same
as the already verified G16f harness.

Unlike a synthetic queue simulator, G16m measures actual timeouts:
queued requests expired before the provider, active provider requests
timed out, late detached workers that were quarantined, and
unchanged original actor minds. It **waits until all late workers
drain**; no late model output may become a personality choice ledger
or a pending ActionRequest after the caller deadline. The chosen
model can only create an *unexecuted* proposal, and no connection to
Evennia is created. Results are interpreted as measured capacity
on the actual runner, **not a fictional world-operations test**.

The structural fixture tests deliberately make all 66 actors succeed
under a fast fake System One backend, then test six distinct characters
with a genuinely slow blocking fake backend: every timed-out actor's
proposed action and second checkpoint must remain absent even after
workers finish. The fake tests are labeled **synthetic** and never
presented as native throughput. The genuine native experiment runs
in a branch-only workflow and records all actual GGUF forwards,
timed-out actor counts, median/P95 successful latency, and queue
telemetry for each population. It must not demand a particular
performance result simply to get green CI: zero on-time decisions
is valid evidence of a failed capacity envelope, not a reason to
fabricate successes.

**Limitations:** this uses the original hypothetical G14 social
menu and G16f synthetic duty recollections, not authenticated 40-crew
Evennia station observations or original duty rosters. Only one
shared native model lane is used; no unsafe shared-engine concurrent
threads or unsupported two-worker speedup are assumed. G16e's
personality-differentiation acceptance does not by itself establish
supervisor acceptance, real high-confidence safety calibration,
or dialogue model quality. The live flag remains OFF.
