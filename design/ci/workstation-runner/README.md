# Workstation runner for model trials

The 16 model-trial jobs (G9–G16 personality, cognition and capacity trials,
about 970 of Ox's CI runner-minutes) can run on the workstation instead of
GitHub's 4-core runners. Nothing changes until the repository variable
`OX_MODEL_RUNNER` is set; deleting it sends the jobs back to GitHub.

## What stays the same

- **CPU only.** Trials still run llama.cpp on the CPU with the threads each
  workflow pins (`n_threads`), so results remain comparable with earlier
  GitHub runs. GPU offload is opt-in through `OX_GGUF_GPU_LAYERS` (default
  `0`); runs with it set are a separate baseline, because offload changes the
  model's floating-point results. Different CPU instruction sets can still
  differ in the last bits, so treat a first workstation run as a check
  against the last GitHub run.
- **Same environment.** Jobs run in an Ubuntu 24.04 container with PostgreSQL
  16, like GitHub's runners, so `setup-python` and the game-managed cluster
  behave the same.

## Security

The repository is public, and a self-hosted runner executes whatever a job
asks. The setup limits that:

- The container is rootless Podman under your user, mounts no host paths,
  and runs jobs as an unprivileged `runner` user.
- Workflows route to it only when the event is not a pull request from a
  fork (the `runs-on` expression checks the head repository), and only the
  model-trial jobs carry that expression.
- In **Settings → Actions → General**, keep "Require approval for all
  external contributors" (or stricter) for fork pull requests.

## Set up (Fedora)

1. Build the image from this folder:
   `podman build -t ox-runner:latest .`
2. Get a registration token: **Settings → Actions → Runners → New
   self-hosted runner** (it expires after an hour; only the first start
   needs it). Put it in `~/.config/ox-runner.env`:
   `OX_RUNNER_TOKEN=<token>`
3. Install and start the service:
   `cp ox-runner.container ~/.config/containers/systemd/`
   `systemctl --user daemon-reload && systemctl --user start ox-runner`
   For it to run while you are logged out: `loginctl enable-linger $USER`.
4. Check it appears as **Idle** under Settings → Actions → Runners, then
   remove the token line from `~/.config/ox-runner.env`.
5. Route the trials to it: **Settings → Secrets and variables → Actions →
   Variables**, add `OX_MODEL_RUNNER` with the value
   `["self-hosted", "linux", "ox-workstation"]`.

Model weights, pip downloads and build outputs persist in the
`ox-runner-cache` volume, so each model downloads once. The runner updates
itself; rebuild the image only to change the toolchain.

## Switching back

Delete the `OX_MODEL_RUNNER` variable. Jobs queued while the workstation is
asleep wait for it, so delete the variable before long absences, or keep
the machine awake.
