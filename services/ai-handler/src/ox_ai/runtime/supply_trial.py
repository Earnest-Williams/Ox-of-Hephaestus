"""Authenticated end-to-end G3c test/operating modes. No direct game DB.

Invoke with prepared five-crew accounts and a real world. All movement uses
CrewNavigator over ordinary Evennia exits; all resource changes use the
actor-bound global WorkReceipt path. Each CLI call is a separate process.
"""
from __future__ import annotations

import asyncio
import json
import sys

from ox_ai.runtime.cooperative_supply import CooperativeSupply
from ox_ai.runtime.five_crew_service import FiveCrewSupervisor
from ox_ai.runtime.work_steps import SimulatedWorkInterruption
from ox_ai.runtime.watch_service import ROOT, atomic_json


async def run(mode: str) -> dict:
    if mode not in ("request", "drop-delivery-ack", "finish"):
        raise ValueError("Unknown G3 supply simulation step")
    supervisor = FiveCrewSupervisor()
    await supervisor.open()
    try:
        cooperation = CooperativeSupply(supervisor)
        if mode == "drop-delivery-ack":
            try:
                await cooperation.advance(drop_delivery_ack=True)
            except SimulatedWorkInterruption:
                print("OX_G3_SUPPLY_DELIVERY_ACK_LOST_ORIGINAL_ID_PERSISTED")
                result = "ack_lost"
            else:
                raise RuntimeError("Expected a real committed delivery and lost ACK")
        else:
            result = await cooperation.advance(stop_after_request=mode == "request")
            required = "requested" if mode == "request" else "completed"
            if result != required:
                raise RuntimeError("G3 supply stage did not reach " + required
                                   + ": " + result)
        record = supervisor.state.get("g3_supply")
        if not isinstance(record, dict):
            raise RuntimeError("No durable G3 private coordination record")
        ids = supervisor.ids
        report = {
            "result": result,
            "order_id": record["work_steps"]["request"]["request_id"],
            "work_steps": record["work_steps"],
            "delivered": record["delivered"],
            "completed": record["completed"],
            "teo_id": ids["teo"],
            "mara_id": ids["mara"],
            "teo_stock_epistemic": supervisor.epistemics["teo"].record[
                "observations"
            ].get("scrubber.spares"),
            "mara_stock_epistemic": supervisor.epistemics["mara"].record[
                "observations"
            ].get("cargo.reserve"),
        }
        atomic_json(ROOT / "g3-supply-report.json", report)
        print("OX_G3_SUPPLY_RESULT", json.dumps({
            "result": result, "order_id": report["order_id"],
            "delivered": report["delivered"], "completed": report["completed"],
        }, sort_keys=True))
        return report
    finally:
        await supervisor.close()


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m ox_ai.runtime.supply_trial request|drop-delivery-ack|finish"
        )
    asyncio.run(run(sys.argv[1]))


if __name__ == "__main__":
    main()
