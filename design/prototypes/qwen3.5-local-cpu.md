# Qwen3.5-0.8B local CPU integration probe

Status: experimental branch only. A green real-model workflow is required
before claiming that live CPU inference worked.

## Goal

Use the existing ox_ai.inference.compatible_chat.CompatibleChatModel with
native Concordia and a real Qwen3.5-0.8B model on a standard CPU-only
GitHub Actions runner. The OpenAI Python library talks only to localhost,
not to a hosted provider. No API secrets or GPU are required.

The probe feeds one synthetic character a directly observed pressure reading,
then offers two world-command proposals: inspect a gauge or defer. Either
valid choice passes. The chosen command stays pending, with no world
command, receipt, mutation, or verified repair. Model errors and invalid
choices fail rather than falling back to the MockModel.

## Workflow and resources

- .github/workflows/ox-qwen-local-cpu.yml is branch-push triggered only
  for named experiment source files on experiment/qwen3.5-0.8b-ci.
  It is also manually dispatchable after being registered on main.
- It is never automatically run on ordinary PRs or main pushes.
- Installs Python 3.12, pinned native Concordia, and the OpenAI SDK.
- Downloads notschmee/Qwen3.5-0.8B-GGUF, Q4_K_M to an Actions cache.
  Records its SHA-256. This preliminary workflow does not freeze the
  upstream Hugging Face revision; deliberately change the cache key when
  selecting a different weight revision.
- Uses a pinned llama.cpp b11819 CPU-only release with SHA-256 verification,
  no GPU offload, non-thinking output, one inference slot, and a 4096-token
  context. Startup and workflow runtimes are bounded.
- Runs existing adapter unit tests plus a new offline native Concordia
  test before starting the real model. Archives probe result, model digest,
  and local server log for seven days.

## What passing means

One real model answered a native Concordia finite-menu prompt, preserving
actor identity and observation revision; the action remained an unconfirmed
proposal. This is not proof of realistic choices, memory A/B improvement,
multi-agent behaviour, 500-turn throughput, or Evennia recovery.

Next steps are bounded repeated-turn latency measurements, matched-evidence
memory interpretation A/B, then opt-in multi-character world experiments.
Do not place this inference workflow in fast PR CI.
