"""Opt-in accelerated clock for the disposable G4h inquiry/restart gate."""

import os

from .settings import *  # noqa: F401,F403

if os.environ.get("OX_INQUIRY_LEARNING_CI") != "1":
    raise RuntimeError("Accelerated investigative-learning CI requires explicit opt-in")

# Five game minutes of evidence review take five wall-clock seconds.
TIME_FACTOR = 60.0
