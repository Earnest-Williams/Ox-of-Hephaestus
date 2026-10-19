# G3d: crew initiative and inspected condition

**Experimental, opt-in implementation.** No operator UI or omniscient handler query.

A game-owned periodic duty window is created with `schedule_rounds(period_game_seconds=...)` in the world (once). The existing game duty script calls `tick_rounds()`. Windows coalesce across long sleeps and carry only a cycle and missed-window count, never latent wear.

The five existing nonprivileged crew receive separate `crew_round_window` observations. With `OX_G3D_INDEPENDENT_ROUNDS=1`, the five-crew handler may individually choose `round_inspect` or defer. Accepted actors use ordinary learned navigation and `inspect <station>`, then file an authenticated, actor-bound, idempotent `oxwork <id> round_report ship <station>`. World validation requires the person to be at the correct fixture, in the correct role, with an actual local inspection of the present state **in the current cycle**. An actor-specific round report is receipted and sent to bridge. Unknown receipt status keeps the original request ID.

The world maintains a simple deterministic, capped wear index on C-01 and A-01, not secretly shared in duty notifications. Once wear reaches 3, an inspected report can discover `maintenance_due`. C-01 `retension` and A-01 `purge` are role/location/fresh-inspection gated preventive actions. They use the global `WorkReceipt` namespace and do not consume cartridges or fix existing failed equipment. The same ID cannot repeat a physical effect.

This slice creates independent *opportunity* and discovery, not broad freeform goal invention. After a world-confirmed report identifies maintenance as due, Mara and Teo make another bounded individual decision whether to perform their permitted preventive operation. Declining is allowed; the report remains authoritative. Unresolved receipt IDs persist across handler restarts, and an unknown effect is never blindly repeated. It does **not** yet provide general delegation, multicycle deadlines, dynamic risk estimates, or freeform goals.

The G3d workflow runs world-only scope/rollback tests and a separate real-server five-client trial: all five crew inspect and file their own world receipt, Mara and Teo independently elect preventive work after private first-hand confirmation, and a handler/world restart preserves physical outcomes. CI uses deterministic Concordia MockModel, which consistently chooses the first offered option; this is not evidence of novel language-based planning. Default worlds remain unchanged until the operator arms the timer and handler separately.
