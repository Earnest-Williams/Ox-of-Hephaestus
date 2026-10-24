# G16k — the proposed one-pass adaptive shortcut changes personality choices

**Result: do not adopt the adaptive shortcut. Post-hoc descriptive analysis
only, dated 24 October 2026.** The data originate from five completed
authentic G16e native Decider Q4 actor shards, not synthetic generated
probabilities. Original [G16e run #40047642031](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40047642031):
Ari, Captain, Lin, Mara and Teo each produced 156 genuine native System One
forwards, totalling **780 recorded passes**. Iona's sixth original shard
timed out at the 150-minute CI cap; the isolated
[Iona recovery #40094100849](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40094100849)
reuses the exact unchanged native protocol. This is five-actor evidence,
**not** an accepted six-actor personality study.

## What was compared

G16c's choice mechanism is **not** simply native argmax. Three
position-balanced semantic probabilities are averaged, each character's
five dispositions induce capped log-score shifts, temperature modifies
predictability, and an actor/decision-keyed BLAKE2b draw chooses the final
action. The original G16 adaptive idea suggested running **one native
pass** and doing the other two only when the initial top-two margin was
below approximately **0.15**. This analysis took the actual first native
vector from each G16e row, applied the **same original saved shifts,
temperature and draw**, and compared the resulting personality final
choice against the original **three-pass** choice. Every original full
three-pass choice was mathematically rederived from its recorded source
probabilities before the comparison; no world command was issued.

To avoid three nearly identical outer-menu orders and repeated-control
pseudoreplication, the primary analysis retains **70 distinct canonical
non-safety actor/scenario/trait combinations** (five actors × seven
non-safety scenes × two profile arms). There are 225 total non-safety
logged rows after including all three caller orders and 15 repeat
controls. **Safety-critical choices were never eligible for one-pass
shortcuts.**

| Initial top-two margin | Early exits / 70 | Different native argmax | Different final personality choice | Max theoretical native forward saving on these 70 |
| ---: | ---: | ---: | ---: | ---: |
| ≥0.05 | 48 | 0 | **8** | 45.7% |
| ≥0.10 | 29 | 0 | **7** | 27.6% |
| **≥0.15** | **20** | **0** | **3** | **19.0%** |
| ≥0.20 | 11 | 0 | **2** | 10.5% |
| ≥0.25 | 6 | 0 | 0 | 5.7% |
| ≥0.30 | 4 | 0 | 0 | 3.8% |

At 0.15, the three differing final action decisions were the Captain's
independent `g16e.peer_review_after_disappointment` choice and Lin's
procedural `g14.approved_watch_relief` and
`g16e.authorized_watch_swap_personal_cost` choices. The initial native
argmax agreed with the three-position argmax for **all 20** early exit
cases; nevertheless the adjusted character decision changed in
**3/20 (15%)**. **Raw argmax agreement is therefore the wrong
acceptance metric for a personality system.**

Under all 260 five-actor logged native decisions (including safety and
repeat/order controls), the 0.15 rule would have omitted 132 of 780
native forwards, a theoretical **16.9%** saving. This arithmetic omits
prompt setup, worker waiting and model-serving overhead, and is **not**
a measured decrease in elapsed latency or queue time.

A higher threshold of 0.25 produced no observed changes among just six
qualifying canonical decisions, but **the threshold was examined after
seeing these same observations**. It cannot be declared safe or
validated from this tiny correlated data set. A future adaptive design
must be **separately preregistered on unseen cases**, comparing the
complete disposition-adjusted final choices, all outer and inner option
positions, urgent/safety exclusions, repeat stability, full scheduler
capacity and authenticated world outcomes.

## Decision

Keep the complete **G15 three-position Decider scoring** in the
proposed G16c path. Do **not** switch on an adaptive first-pass heuristic
or treat it as a default optimization. [G16f measured throughput](g16f-native-throughput-results-2026-10-24.md),
[G16i hypothetical queue modeling](g16i-scheduler-admission-envelope.md)
and [G16j actual scheduler observability](https://github.com/Earnest-Williams/Ox-of-Hephaestus/blob/experiment/g16j-scheduler-queue-telemetry/design/prototypes/g16j-scheduler-queue-observability.md)
are independent capacity work; none establishes that a scoring shortcut
preserves character behaviour. The original G16e preregistration and
native results remain unchanged.
