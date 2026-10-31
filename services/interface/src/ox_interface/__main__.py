"""Terminal rendering of the P5 acceptance view (no browser stack yet).

SKETCH. ``python -m ox_interface --world http://127.0.0.1:4001 \\
    --handler http://127.0.0.1:8711 --character '#12'`` with
``OX_DEV_SESSION`` and ``OX_HANDLER_TOKEN`` in the environment.
"""

from __future__ import annotations

import argparse
import os

import polars as pl

from ox_interface.clients.handler import HandlerInspectionClient
from ox_interface.clients.world import WorldReadClient
from ox_interface.views.belief_vs_actual import belief_vs_actual


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("--world", required=True)
    parser.add_argument("--handler", required=True)
    parser.add_argument("--character", required=True)
    args: argparse.Namespace = parser.parse_args()
    world_url: str = args.world
    handler_url: str = args.handler
    character: str = args.character
    world: WorldReadClient = WorldReadClient(world_url, os.environ["OX_DEV_SESSION"])
    handler: HandlerInspectionClient = HandlerInspectionClient(
        handler_url, os.environ["OX_HANDLER_TOKEN"]
    )
    inspection = handler.epistemics(character)
    if inspection is None:
        raise SystemExit("No inspectable character (or not authorized).")
    table: pl.DataFrame = belief_vs_actual(world.snapshot(), inspection)
    with pl.Config(tbl_rows=200, tbl_cols=12):
        print(table)


if __name__ == "__main__":
    main()
