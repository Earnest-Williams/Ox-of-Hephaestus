# G11 — World-authenticated personality decisions (2026-10-23)

**Implementation:** [PR #106](https://github.com/Earnest-Williams/Ox-of-Hephaestus/pull/106) (G11 opt-in, production unchanged).

**Three-seed evidence:** [Actions run #39881548281](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39881548281), [complete aggregated three-seed report](https://github.com/Earnest-Williams/Ox-of-Hephaestus/actions/runs/39881548281/artifacts/12472320488).

The prior G10 study tested hypothetical planning options. G11 instead exercises actual authorization: for a **genuinely pending agreement** between two co-located, separately authenticated crew characters, the recipient's personality routing selects a GOAP or Decider Q4_K_M proposal to accept, defer, or decline. That proposal changes world state **only** through Evennia's existing durable `social_reply` transaction and its independently addressed observation. Two real equipment incidents are also repaired in each 205-turn world.

## Three independently executed worlds

| Seed | Authenticated crew turns | World agreement reply receipts | Decider replies | GOAP replies | Different from GOAP | World outcomes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 241 | 205 | 7 | 4 | 3 | 3 | Accept 3; decline 2; defer 2 |
| 619 | 205 | 7 | 3 | 4 | 2 | Accept 1; decline 1; defer 5 |
| 1009 | 205 | 7 | 4 | 3 | 3 | Accept 2; decline 0; defer 5 |
| **All** | **615** | **21** | **11** | **10** | **8** | **Accept 6; decline 3; defer 12** |

All three parallel actual-world trials and the cross-seed aggregator passed. The experiments also verified **15 separate authoritative maintenance work receipts**, across six actual operator-injected equipment incidents (one cargo, one scrubber, in each seed). All three independently inspected final equipment states were repaired.

## Examples with actual world receipts

The following outcomes are real persistent social states inside the disposable Evennia game, **not imagined follow-on storytelling**.

- **Seed 241, turns 9 and 201:** Iona twice received a pending commitment from Ari. On both occasions the GOAP baseline favored acceptance, but Decider chose **decline** and two distinct world transactions recorded rejection. This is a repeated in-world pattern, though still only two examples.
- **Seed 241, turn 27:** Iona's baseline would have declined the Captain's pending commitment; Decider deferred instead.
- **Seed 619, turn 21:** Iona considered the Captain's pending commitment. GOAP would have declined; the Decider route also declined and the world recorded that decline.
- **Seed 619, turn 22:** Mara's baseline would have accepted a pending commitment with Lin. Decider instead deferred, and Evennia recorded deferral.
- **Seed 619, turn 50:** Ari's symbolic baseline was acceptance with Lin; Decider deferred and the world recorded deferral.
- **Seed 1009, turn 4:** Mara's GOAP baseline was acceptance with Lin; Decider deferred.
- **Seed 1009, turn 9:** Iona's GOAP baseline was acceptance with Ari; Decider deferred.
- **Seed 1009, turn 195:** Iona's GOAP baseline was decline with the Captain; Decider deferred.

Every example includes a unique successful world work request, a server-issued source event ID, and an independently addressed counterpart observation. Private memory/interpretation does not grant authorization, and a model preference alone does not create a relationship.

## What we learned and what remains

Across three seeds, **8 of 11 real Decider consultations selected different social actions from GOAP**, and the divergences were actual world-authorized relationship state changes. That fulfills a central goal of occasional *character-dependent deviation from procedural optimization* without forcing a wrong choice or risking unauthorized equipment control. But most deviations favored **deferral**, potentially reflecting a risk-avoiding response bias rather than rich personality.

The 21 decisions were concentrated in the recipient characters who actually received world pending commitments; there were **11 Iona, 4 Ari, 4 Mara, 2 Lin, 0 Captain and 0 Teo reply occasions**. That is a property of who was addressed, **not** proof the latter two would always choose GOAP. A larger world with more distributed opportunities is needed to compare all six fairly.

Relationship agreement **acceptance is not fulfillment**. The separate real-world social contract logic still demands appropriate agreement-specific evidence for performance; G11 does not manufacture any subsequent intimate, financial or physical fulfillment. It does not assert that a defer or decline is a mistake. The production supervisor remains disabled, and the G8/G9 baselines are unchanged by default.

The next scientific control would hold identical world-observed evidence and pending-agreement details constant while varying only the actor's personality vector, using forked read-only character states. This is necessary to distinguish stable personality effects from personal memory and counterpart-availability confounds.
