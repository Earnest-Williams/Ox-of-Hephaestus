# G2 character factory — foundation slice

## Purpose and authority

Introduce a versioned, deterministic, model-free character blueprint. It describes a prospective person's initial tendencies, occupational knowledge, narrative history, and estimated starting skills. It is **not** a world-owned skill, certification, employment contract, character body, or permission.

The existing Concordia CrewAgent optionally receives a CrewBlueprint. Each instantiated mind retains its own identity, memory, observations, requests, and checkpoint. An unmodified legacy checkpoint without a profile continues to restore. The author-created profile cannot execute world work: Evennia alone authorizes and records effects.

## Composition

Construct a fully custom person without templates, or combine zero or more occupation and personality presets. All ten continuous trait dimensions have integer range 0–100: OCEAN plus risk tolerance, authority challenge, collaboration, uncertainty tolerance, and stress recovery. Default 50 is neutral. The sixteen MBTI-inspired archetypes are narrative style presets only, not psychometrically valid predictive categories or a second hidden trait transformation.

Conflicting numerical personality presets must be resolved by explicit overrides; overlapping occupational skill estimates take the maximum instead of being summed as fictitious practice. The generated profile retains template identifiers for provenance and supports lossless versioned JSON round-tripping. Historical memory and world receipts are not in the blueprint.

## Scope and future increments

This first PR adds the factory, optional Concordia context, and regression tests. It does not replace the five existing role-bound service constructors or migrate existing character identities. It does not implement interviewing, a recruitment interface, candidate economics, job contracts, actual skills, memory transplant, or agent behaviour predictions.

Next: wire the factory into runtime with stable world-owned person identity and explicit legacy migration; exercise nonblocking personality-influenced choices with the same offered capabilities; add world-owned competencies and training; create a finite dock-local candidate supply with persistent dossiers and imperfect evidence; add costed delayed specialist search and vacancy consequences; finally employment contracts, departures, and rehire.

## Verification

Run the model-free suite with Python 3.12+:

    python -m pip install -e ./services/ai-handler
    python -m unittest discover -s services/ai-handler/tests -p 'test_character_factory.py' -v

With pinned Concordia installed, the same suite also checks independent native minds, private observations, profile checkpoint restoration and identity mismatch rejection. All pre-existing Ox workflows remain required before merge.