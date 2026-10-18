# Scenario 0 — Watch handover

**Fixture specification only. Not yet executable.**

## Setup

Two distinct crew characters occupy accessible parts of a small ship. One is completing engineering watch, the other is about to relieve them. The active roster, time and character locations belong to the mock world (and later to Evennia).

## Test

The outgoing watchkeeper communicates a legitimate outstanding concern to the incoming watchkeeper. The recipient must be present or reached through a valid in-world communications action. After handover, the incoming character should know what they were told, while an uninvolved third party would not gain the same information automatically.

## Evidence to capture

- Game events and observations scoped to each participant.
- Distinct private memories of the handover.
- Correct handover timing and no duplicate physical actions after reconnect.
- Model request count and no inference during an entirely quiet interval unless a scheduled duty wake-up occurs.

## Purpose

Prove entity creation, observation, routine communication, wake-up scheduling, memory, and WorldPort transport before building ship machinery.
