# G7 pilot — GOAP for emotional and interpersonal behavior

**Purpose:** test the existing independent GOAP planner on a social exchange,
not build out the ship and not generate an illustration. This is an isolated
experimental scene with one small apartment and two adult people: Clara (the
resident) and Ben (her guest). They have returned from a date and are talking
about having enjoyed their evening together.

## The world and the minds

- **Evennia owns:** a persistent room, two separate physical characters,
  actual location and the words transmitted by ordinary character say.
  The live test authenticates two different nonprivileged bot accounts and
  confirms delivery of each spoken line to BOTH clients.
- **Each GOAP agent owns privately:** interest in another date, caution about
  moving quickly, its remembered utterances, provisional interpretations,
  pursued goals and plans from the shared GoapPlanner.
- **Not shared:** numerical private preferences, another person's imagined
  intentions, the other GOAP trace or world-certified feelings.
  Enjoying a date is not consent or a commitment to another date.
- **GOAP operators** describe possible social acts, preconditions,
  costs and projected *speaker-owned* facts. GOAP considers competing
  goals and minimum-cost paths. An attempted line's projected result is
  adopted only after the real world (or labeled offline test room) confirms
  it was spoken.
- **Listener inference** uses only the words actually heard and a small,
  explicit utterance-to-cue vocabulary. This is not general natural
  language understanding.

The scene is separate from the freighter. Ship bootstrap does not create it.
The experiment exercises the general planner, not equipment-specific GOAP.

## Experimental variants

All start after a pleasant date, without prescribing romance:

| Variant | Private motives | What to test |
| --- | --- | --- |
| cautious | Clara likes Ben but wants to move slowly | Ben should acknowledge a stated pace rather than pressure her |
| mutual | Both interested and comfortable | A second-date invitation may be made and accepted |
| mismatch | Clara interested; Ben enjoyed the date but not interested in another | Ben may decline and Clara should respect that |

Fixed sentences are used ONLY as surface realizations of the GOAP-chosen
actions, not as a predefined conversation transcript. Goal priorities,
minimum-cost plans and observed responses determine the action sequence.
There is no model call.

## Acceptance questions

1. A positive utterance is evidence of an enjoyable evening, never a
   future commitment or an authorization to make assumptions about consent.
2. The planner can find a multi-step social plan; only its first action is
   issued, and a new observation can change the next plan.
3. Stated boundaries change what is offered and pursued. Neither person's
   private goals are transmitted as if they were speech.
4. Failed or unconfirmed speech cannot produce a fictional completed action.
5. Distinct motives can produce different traces in the same room.
6. The default trial uses 24 turns maximum. If both participants do not
   reach an ending, it reports turn_capped, never a fake happy ending.

## Reproduction

~~~sh
python -m pip install -e ./services/ai-handler
python -m unittest discover -s services/ai-handler/tests \
  -p test_social_apartment_goap.py -v
python services/ai-handler/src/ox_ai/scenarios/apartment_goap.py \
  --variant cautious --turn-cap 24
cd game
python -m world.test_runner world.tests.test_social_apartment --verbosity=2
~~~

The isolated [G7 GitHub Actions workflow](../../.github/workflows/ox-g7-social-goap.yml)
also provisions two separate actual bot accounts, starts real Evennia,
and executes [one live conversation](../../scenarios/apartment_goap/live_trial.py)
with normal say commands. Speaker and listener must each observe the
world's output before a GOAP utterance is marked complete. It runs no
hosted-model trials and no six-crew or inherited Evennia matrix.

## Explicit nonclaims

This tests social **intent selection and response to spoken signals**.
It does not yet prove humanlike emotion, dynamic attachment, general
language understanding, spontaneous expressive speech, or durable
free-text replay across disconnects. The world does not award romance
points for an utterance.

Next, examine the distinct traces, then consider private dynamic
emotional-state updates (comfort, anxiety, hope, disappointment) and how
the same words affect different personalities. Any later language generator
must remain subordinate to GOAP action selection and actual world events.
