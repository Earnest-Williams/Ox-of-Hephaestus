"""Opt-in accelerated clock for the disposable G4g transport/restart gate."""

import os

from .settings import *  # noqa: F401,F403

if os.environ.get("OX_CONCEPT_LEARNING_CI") != "1":
    raise RuntimeError("Accelerated conceptual-learning CI requires explicit opt-in")

# Fifteen game minutes of supervised work take fifteen wall-clock seconds.
# The ordinary game settings and curriculum duration remain unchanged.
TIME_FACTOR = 60.0
