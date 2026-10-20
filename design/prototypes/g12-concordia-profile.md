# G12 — profile before modifying Concordia

The `concordia_scale.py` profiler instantiates **6, 20 and 40 independent
native Concordia crew brains**, with private seeded and observed episodes.
It measures native decision dispatch through Concordia's real context
components (using a deterministic local `sample_choice` backend), time to
fork an inference snapshot, serialised checkpoint size, Python-traced peak
allocations, prompt character length and optional per-choice JSONL/fsync
diagnostic overhead.

It does **not** measure hosted model inference latency, actual tokenizer
output, GPU use, database persistence or true process RSS. Neither an
unusually slow public CI runner nor a fast local backend is evidence about
Gemini response time.

The dedicated PR workflow runs only when this profiler or its workflow
changes. It does not schedule G8's 500-decision experiment and has no
network-inference cost. It preserves raw JSON results as a GitHub Actions
artifact. No removal of Concordia observation storage, component dispatch
or optional providers is authorised without inspecting these measurements
and running compatibility checks.

For reproducing:
```
python scenarios/profiling/concordia_scale.py --rounds 2 \
  --output /tmp/ox-g12-native.json
```
