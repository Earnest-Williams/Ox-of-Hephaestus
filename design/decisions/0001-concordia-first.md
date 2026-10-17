# ADR 0001 — Concordia is the first cognitive foundation

**Status:** Accepted for Prototype 1 — 2026-10-18

## Context

Ox needs persistent, distinct NPCs with perception, memory, goals, social judgment and autonomy. Building all cognitive components around generic model-call infrastructure would duplicate work. [Concordia](https://github.com/google-deepmind/concordia) already provides composable entities, cognitive components, snapshots and rich logging.

## Decision

- **Use Concordia's entity and component APIs** for NPC cognition. An Ox handler process supervises those entities, model demand, persistence and world connection.
- Begin with `EntityAgentWithLogging`, observation components, `ListMemory`, and a small Ox-specific acting policy. Use richer perception/planning components selectively; avoid an expensive multi-call cognition graph for every routine action.
- Write duty/commitment/procedure components in the Ox package. Actual character skill, physical condition and official orders remain game facts.
- Do not add PydanticAI or LangGraph in Prototype 1; revisit if a demonstrated limitation warrants another orchestration framework.
- Keep the inference provider swappable. The existing Concordia OpenAI-compatible adapter is a candidate for a local inference server, but no model or backend is mandated.

## Reproducibility and licence

The package's **distribution name is `gdm-concordia`**, import namespace `concordia`, licence **Apache-2.0**. We do not copy vendor code into the Ox repository.

The published **v2.4.0** source lacks `interrupt_driven.py` and `interrupt_scheduling.py` examined in current upstream `main`. Prototype work targeting those features must therefore use the **pinned source revision**:

```text
google-deepmind/concordia @ 4b7e02a94b719e56f10989046af32d79bbbc3b9c
```

The optional `[concordia]` dependency in `services/ai-handler/pyproject.toml` records this provisional pin; it is not installed by default. Do not replace it with unpinned `main` or assume PyPI 2.4.0 contains the same features. Lock transitive dependencies after the first successful integration tests. Review upstream licence/NOTICE obligations and model-weight licences separately before distribution.

## Consequences and review trigger

We inherit Concordia's synchronous entity lifecycle and component-state conventions. Ox still needs its own scheduler, durable state management and action-outcome boundary for a live server. If the cognitive component interfaces prove brittle or require too many model calls, reassess after a controlled prototype using equivalent observations and a common model.
