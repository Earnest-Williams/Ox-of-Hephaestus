"""OX_GGUF_GPU_LAYERS: CPU-only unless explicitly opted in."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from ox_ai.inference.decider_gguf_choice import GPU_LAYERS_ENV, gpu_layers


class GpuLayersTests(unittest.TestCase):
    def test_default_is_cpu_only(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(gpu_layers(), 0)

    def test_explicit_offload(self) -> None:
        with mock.patch.dict(os.environ, {GPU_LAYERS_ENV: "99"}):
            self.assertEqual(gpu_layers(), 99)

    def test_rejects_non_integer(self) -> None:
        for bad in ("-1", "all", "1.5"):
            with mock.patch.dict(os.environ, {GPU_LAYERS_ENV: bad}):
                with self.assertRaises(ValueError):
                    gpu_layers()


if __name__ == "__main__":
    unittest.main()
