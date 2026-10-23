# G11 — real-model, matched-evidence native Concordia A/B

This is a pilot, not a claim that memories improve real-world behaviour.
Four predeclared, synthetic choice fixtures test a recanted promise,
contradictory cargo evidence, confidentiality and repetition after refusal.

Both arms use the identical character identity, native Concordia observation
history, private typed episodic records, seeds and finite offered commands.
Only the additional Ox read-only private-memory projection differs.
`CrewAgent(memory_projection_enabled=False)` is an explicit control arm.
The mode persists through forks/checkpoints. It never alters Evennia authority.

Only the manually dispatched `Ox G11 matched-evidence memory A/B` workflow
uses hosted Gemini. One to three repetitions require **8–24 API requests**;
the provider key must exist in Actions secrets. It is not automatic PR CI.

The experimental Qwen CPU branch additionally supports
`--provider qwen-local` using an OpenAI-compatible localhost endpoint.
This is **real model inference**, unlike `capture`, but it is not hosted
inference or an automatic G11 production gate. The isolated
`ox-qwen-local-cpu.yml` runner records descriptive per-case behaviour and
latency while preserving exactly the same G11 fixtures and actor-visible
evidence; only provider choice and memory-context projection vary.

A local smoke command tests *wiring only*, not model behaviour:

```
python scenarios/g11_memory_ab_trial.py --provider capture \
  --repetitions 1 --output /tmp/g11-smoke.json
```

Results include selected verbs, narrow predeclared expected-action matches,
confidentiality/repetition warning counts, prompt size and request latency.
The smoke-only output explicitly marks quality evidence invalid.

Before adopting augmented memory on behavioural grounds, expand to blinded
cases, repeated runs, multiple models and outcome-level human adjudication.
The synthetic labels themselves are not world action authorisations.
