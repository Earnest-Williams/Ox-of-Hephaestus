"""P5 minimal acceptance view: G19 actual state beside an engineer's belief.

SKETCH. Pure Polars join of two independently authorized reads:

- the developer ``ox.world.read/1`` series (actual cell state, Evennia-owned);
- one character's ``ox.handler.inspect/1`` page (their panel evidence).

The view never infers a belief from world state or the reverse. A panel the
engineer never read does not appear. ``verified`` uses the same rule as
``AgentEpistemics.assess``, evaluated at the world page's game time, so a
belief can be correct, wrong, or right-but-expired, and the row says which.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import polars as pl
from ox_contracts.handler_inspection import InspectionPage
from ox_contracts.world_read_model import DeveloperWorldPage

PANEL_PREFIX: Final[str] = "g19.panel."
CELL_METRICS: Final[tuple[str, ...]] = (
    "pressure_kpa",
    "oxygen_kpa",
    "temperature_k",
)

ACTUAL_SCHEMA: Final[dict[str, pl.DataType]] = {
    "panel_key": pl.String(),
    "panel_id": pl.String(),
    "space_id": pl.String(),
    "cell_id": pl.String(),
    "metric": pl.String(),
    "actual": pl.Float64(),
}
BELIEF_SCHEMA: Final[dict[str, pl.DataType]] = {
    "panel_key": pl.String(),
    "metric": pl.String(),
    "believed": pl.Float64(),
    "observed_game_s": pl.Float64(),
    "valid_for_s": pl.Float64(),
    "evidence_id": pl.String(),
}


def actual_frame(pages: Sequence[DeveloperWorldPage]) -> pl.DataFrame:
    """Panel → room → gas cell → actual cell metrics, from Evennia only."""
    cell_of: dict[str, str | None] = {
        space.space_id: space.pressure_cell_id
        for page in pages
        for space in page.spaces
    }
    cells: dict[str, dict[str, float]] = {
        cell.cell_id: {
            "pressure_kpa": cell.pressure_kpa,
            "oxygen_kpa": cell.oxygen_kpa,
            "temperature_k": cell.temperature_k,
        }
        for page in pages
        for cell in page.pressure_cells
    }
    rows: list[dict[str, object]] = []
    for page in pages:
        for unit in page.equipment:
            cell_id: str | None = cell_of.get(unit.space_id)
            if cell_id is None or cell_id not in cells:
                continue
            for metric in CELL_METRICS:
                rows.append(
                    {
                        "panel_key": unit.equipment_id.lower(),
                        "panel_id": unit.equipment_id,
                        "space_id": unit.space_id,
                        "cell_id": cell_id,
                        "metric": metric,
                        "actual": cells[cell_id][metric],
                    }
                )
    return pl.DataFrame(rows, schema=ACTUAL_SCHEMA)


def belief_frame(inspection: InspectionPage) -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    for observation in inspection.observations:
        if not observation.fact.startswith(PANEL_PREFIX):
            continue
        panel_key, _, metric = observation.fact[len(PANEL_PREFIX) :].rpartition(".")
        value: object = observation.value
        if metric not in CELL_METRICS or isinstance(value, bool):
            continue
        if not isinstance(value, (int, float)):
            continue
        rows.append(
            {
                "panel_key": panel_key,
                "metric": metric,
                "believed": float(value),
                "observed_game_s": observation.observed_game_s,
                "valid_for_s": observation.valid_for_s,
                "evidence_id": observation.evidence_id,
            }
        )
    return pl.DataFrame(rows, schema=BELIEF_SCHEMA)


def belief_vs_actual(
    pages: Sequence[DeveloperWorldPage], inspection: InspectionPage
) -> pl.DataFrame:
    if not pages:
        raise ValueError("No world snapshot")
    world_now: float = pages[0].game_time_s
    joined: pl.DataFrame = belief_frame(inspection).join(
        actual_frame(pages), on=["panel_key", "metric"], how="left"
    )
    return (
        joined.with_columns(
            pl.lit(world_now).alias("world_game_s"),
            (pl.lit(world_now) - pl.col("observed_game_s")).alias("belief_age_s"),
            (
                (pl.col("observed_game_s") <= world_now)
                & (
                    pl.lit(world_now)
                    <= pl.col("observed_game_s") + pl.col("valid_for_s")
                )
            ).alias("verified"),
            (pl.col("believed") - pl.col("actual")).alias("delta"),
        )
        .select(
            "panel_id",
            "space_id",
            "cell_id",
            "metric",
            "believed",
            "actual",
            "delta",
            "belief_age_s",
            "verified",
            "evidence_id",
        )
        .sort(["panel_id", "metric"])
    )
