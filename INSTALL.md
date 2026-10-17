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

This is a **framework smoke test**, not an Ox-specific playable build. In particular, there is no separate AI handler to launch yet.

The upstream [Evennia setup guide](https://www.evennia.com/docs/latest/Setup/Setup-Overview.html) is the authoritative source for engine installation details and platform-specific requirements.

For the intended Ox components and development sequence, read [README.md](README.md) and [ARCHITECTURE.md](ARCHITECTURE.md). Do not rename or republish the inherited `evennia` Python package as Ox as part of this documentation setup.
