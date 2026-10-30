"""One gas heat capacity for every module that touches pressure-cell energy.

The physics clock defines cell energy as (capacity + mass * cp) * T and
rebuilds it from the stored temperature on every tick. A module that converts
energy to temperature with a different cp silently creates or destroys heat at
each tick boundary. Fuzz finding F4-1 was exactly this: crew physiology used
1.005 against the clock's 1.0, cooling every occupied cell by ~0.4 K per tick.

This test reads the source, so it needs no Django or database.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from typing import Final

WORLD: Final[Path] = Path(__file__).resolve().parents[1]
CLOCK: Final[Path] = WORLD / "continuous_ship_physics.py"
CLOCK_CONSTANT: Final[str] = "CP_GAS_KJ_KG_K"
FORBIDDEN_LITERALS: Final[frozenset[float]] = frozenset({1.005, 1.0045, 0.718})


def _module_constants(path: Path) -> dict[str, float]:
    tree: ast.Module = ast.parse(path.read_text(encoding="utf-8"))
    found: dict[str, float] = {}
    node: ast.stmt
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            value: object = node.value.value
            if isinstance(value, float) and not isinstance(value, bool):
                target: ast.expr
                for target in node.targets:
                    if isinstance(target, ast.Name) and "CP" in target.id:
                        found[target.id] = value
    return found


class HeatCapacityConsistency(unittest.TestCase):
    def test_every_gas_cp_constant_matches_the_physics_clock(self) -> None:
        clock_cp: float = _module_constants(CLOCK)[CLOCK_CONSTANT]
        checked: int = 0
        path: Path
        for path in sorted(WORLD.glob("*.py")):
            name: str
            value: float
            for name, value in _module_constants(path).items():
                with self.subTest(module=path.name, constant=name):
                    self.assertEqual(value, clock_cp)
                checked += 1
        self.assertGreaterEqual(checked, 6)

    def test_no_inline_alternative_air_heat_capacity(self) -> None:
        path: Path
        for path in sorted(WORLD.glob("*.py")):
            tree: ast.Module = ast.parse(path.read_text(encoding="utf-8"))
            node: ast.AST
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, float)
                    and node.value in FORBIDDEN_LITERALS
                ):
                    self.fail(f"{path.name}:{node.lineno} uses cp literal {node.value}")


if __name__ == "__main__":
    unittest.main()
