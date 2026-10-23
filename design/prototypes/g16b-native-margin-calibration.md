# G16b — native margin calibration, frozen before G16e

**Status:** descriptive, two real G14 v2 Decider Q4_K_M runs verified; **proposed defaults frozen for future G16e**, not production adoption. **Date:** 24 October 2026. Machine-readable record: [G16b calibration v1](g16b-calibration-v1.json).

## Direct native evidence, not synthetic model scores

The six actor-specific role artifacts were recovered for **both** successful G14 v2 Actions runs:

- [First position-balanced v2 run #40016163471](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40016163471).
- [Exact-PR-head rerun #40028008764](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/40028008764).

Each run had six identical authenticated G9 source-role identities (Lin, Ari, Iona, Mara, Teo, Captain), 312 native calls (288 factorial + 24 repeats), three cyclic menu orders, all 24 within-run repeated-choice controls and **zero Evennia commands**. The 12 artifact ZIPs contain 48 factorial rows per actor and four repeat controls. Artifact identifiers, original run, final-head run, and the validation summary are preserved in the JSON record. The archives themselves are subject to GitHub retention.

For each **numeric_original** actor × case, the three code-position vectors were remapped to their stable semantic actions and **averaged across A/B/C**. The largest and second-largest averaged probabilities define the native top-two *probability margin* and the natural-log score gap \(g = \ln(p_1/p_2)\). There are **24 actor/case baselines per run, 48 paired measurements across two runs**, not 48 independent actors or new situations. Complete role, native engine, source-run identity, evidence digest, factorial coverage, position balance, repeat prompt hash, offered menu, selected argmax and probability-vector validity were checked before pooling.

| Statistic over both native runs | Measured |
| --- | ---: |
| Median top native semantic score | **0.41005** |
| Highest top native semantic score | **0.52923** |
| Top-two probability margin, P25 / median / P75 | **0.04703 / 0.08080 / 0.16043** |
| Top-two log probability gap, P25 / median / P75 | **0.13141 / 0.22727 / 0.41287** |
| Maximum top-two probability margin | **0.27957** |
| Actor/case summaries with margin below 0.30 | **48/48** |
| Actor/case summaries with native top score at least 0.85 | **0/48** |
| Three-position averaged winning actions differing between v2 runs | **0/24** |

These figures explain an important distinction: the first-position native response changes between the two runs in some matched conditions, but the three-position **averaged** winner stays the same for all 24 actor/case baselines. That is evidence for *this protocol's* averaged-winner stability, not general robustness to other menus or demonstrated natural personality.

## Frozen, auditable G16c defaults

| Parameter | Initial value | Pre-G16e selection rule |
| --- | ---: | --- |
| \`gain\` | **0.10** | Half the capped shift magnitude, assuming a two-unit typical signed tag contrast (author assumption) |
| \`max_shift\` | **0.21 log-score units** | Round half the observed P75 log probability gap to two decimals |
| Base sampling temperature | **0.33** | Round median observed log gap / ln(2): median native top-vs-runner odds become about 2:1 after temperature scaling |
| Per-person temperature range | **0.20–0.45** | Authored bounded range, not estimated from G14 |
| Urgent temperature | **0.11** | Round base temperature / 3; must not replace a world safety gate |
| Proposed safety evidence lock | **0.85** | Previously proposed heuristic, **not calibrated from these G14 scores** |

For an authored person with 0–100 psychological scores, preregister

\[
T_{\rm person} = \operatorname{clamp}\!\left(0.33\left[1 + 0.25\frac{\text{risk tolerance} - \text{conscientiousness}}{100}\right],\,0.20,\,0.45\right).
\]

A declared urgent boundary instead uses \`0.11\`. No G16e responses were examined when selecting these numbers, and they must **not** be retuned against the same G16e holdout and still described as one preregistered test. The \`gain\` and \`max_shift\` calculations are controlled heuristics matched to a *native score scale*; they are **not** statistically fitted psychological parameters or proof that 25% paired-choice differentiation will be achieved.

### Safety correction required before integration

**The proposed \`evidence_lock=0.85\` engaged on zero G14 cases.** The highest top semantic score was about 0.53, including the life-support-spare hypothetical; a 0.85 threshold cannot be claimed to protect real safety-critical menus on this evidence. Native Decider scores are relative option logits, **not calibrated probabilities of real-world correctness**.

When a genuinely safety-critical, independently authored evidence-lock rule applies, G16c must **force the native highest-scored semantic action** (stable semantic-key tie-break). Merely setting personality shifts to zero while making a seeded temperature draw still permits a lower-ranked option. Even that locked winner is only a *proposal* and remains subject to Evennia's independent authorization, locality, role, equipment and work-receipt checks. Critical cases lacking a justified lock require an explicitly authored safety policy; they must not inherit a fallback based solely on a weak raw top score.

The earlier G16e wording calls for at least four scenarios with top-two margin below 0.30. **All four G14 case types already satisfy that numeric criterion**, although two have strongly unanimous native *argmax* choices (watch relief and private apology). Therefore the new G16e scenes must be preregistered to test **genuine meaningful action alternatives** and report choice diversity, not merely filter on a low margin and claim a non-ceiling behavioural experiment.

## Next acceptance boundary

The exact tag values are in the separate merged [G16a contract catalog](../../contracts/ox_contracts/data/personality_action_tags.v1.json). G16c may implement this frozen score calibration and replay ledger only behind \`OX_PERSONALITY_CHOICE\` (off by default), with no new Evennia authority. G16d must preserve GOAP's positive fractional cost semantics and deterministic search ordering. G16e must explicitly test the safety-lock and semantic menu-permutation cases against native actor-brain evidence before any claim of behavioural adoption. G16f must time three forwards at 6, 20 and 40 actors; the historical single-pass 7.7-second CPU median is not a 40-actor throughput measurement.
