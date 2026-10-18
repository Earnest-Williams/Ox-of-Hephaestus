# Development setup

> **Current status:** This checkout is still primarily the **Evennia framework**. The steps below create and run a stock Evennia development game. They do **not** install a completed Ox of Hephaestus spaceship simulation or AI handler.

## Requirements

- Python **3.12 or later**, as required by the inherited `pyproject.toml`.
- A Python virtual environment and the normal Evennia dependencies.

## Run a baseline Evennia game

From the repository root:

```sh
python -m venv .venv
# Activate .venv for your shell, then:
python -m pip install -e .
evennia --init ox-dev
cd ox-dev
evennia migrate
evennia start
```

Evennia's standard local development client is available at `http://localhost:4001`, and traditional MUD clients can connect to `localhost:4000` with the default settings.

This is a **framework smoke test**, not an Ox-specific playable build. In particular, there is no running AI handler or ship-specific game to launch yet.

## Install the independent service skeletons

These are **importable Python packages, not running daemons**. From the repository root in a Python 3.12+ virtual environment:

```sh
python -m pip install -e ./services/ai-handler
python -m pip install -e ./services/interface
python -m unittest discover -s services/ai-handler/tests -v
```

When beginning Concordia integration, opt into the pinned source dependency:

```sh
python -m pip install -e "./services/ai-handler[concordia]"
```

This requires Git and network access; the released `gdm-concordia==2.4.0` package does not include the interrupt-driven scheduler used in our design. The model server, Concordia integration, NPC client logins and UI server are **not yet provided**. Use separate environments if the service dependencies diverge.

See the [AI handler README](services/ai-handler/README.md), [interface README](services/interface/README.md) and [Prototype 1 plan](design/prototypes/01-autonomous-crew.md).

The upstream [Evennia setup guide](https://www.evennia.com/docs/latest/Setup/Setup-Overview.html) is the authoritative source for engine installation details and platform-specific requirements.

For the intended Ox components and development sequence, read [README.md](README.md) and [ARCHITECTURE.md](ARCHITECTURE.md). Do not rename or republish the inherited `evennia` Python package as Ox as part of this documentation setup.
