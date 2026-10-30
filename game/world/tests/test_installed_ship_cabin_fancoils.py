"""Installed G19: forty real cabin thermal appliances and original circuits."""
from collections import defaultdict, deque

from evennia.utils.test_resources import EvenniaTestCase

from world.bootstrap import build_ship
from world.full_ship_operations import (
    install_candidate, install_pressure_cells, initialize_nominal_atmosphere,
    state, set_isolator, set_component_condition,
)
from world.ship_world import build_canonical_ship, find_ship_space
from world.models import CanonicalShipState, WorkReceipt
from world.continuous_ship_physics import (
    PhysicsError, arm_continuous_physics, commission_g19_electrical,
    commission_g19_cabin_coils, configure_scenario_casualty,
    crew_physical_action, tick_continuous_physics, local_physics_readout,
    _clock,
)
from world.ship_cabin_fancoils import FANCOILS


class InstalledCabinFanCoils(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        build_canonical_ship()
        install_candidate(operator_approved=True)
        install_pressure_cells(operator_approved=True)
        initialize_nominal_atmosphere(operator_approved=True)
        arm_continuous_physics(operator_approved=True, now_game_time=1000)
        self.worker = build_ship()["watch"]
        set_isolator("ISO-GEN-M", "closed", operator=True)
        commission_g19_electrical(operator_approved=True)
        self.now=1000
        self.serial=900

    def at(self, room):
        self.assertTrue(self.worker.move_to(
            find_ship_space(room), quiet=True), room)

    def operation(self, name, value, request=None):
        if request is None:
            self.serial+=1
            request=f"{self.serial:032x}"
        return crew_physical_action(
            self.worker,request,"cabin_air",name,value)

    def power_route(self, destination, source="NODE-GEN-M"):
        """Close only original installed contacts along a real source path."""
        edges=CanonicalShipState.objects.filter(category="edge")
        graph=defaultdict(list)
        for edge in edges:
            spec=edge.reference
            if spec.get("network")!="power" or edge.condition in {
                    "faulted","failed","severed","jammed","destroyed"
            } or edge.setting!="available":
                continue
            graph[spec["from_node"]].append((spec["to_node"],edge))
            if spec["kind"] in {"bridge_feeder","cross_tie"}:
                graph[spec["to_node"]].append((spec["from_node"],edge))
        q=deque([source])
        previous={}
        seen={source}
        while q and destination not in seen:
            for node,edge in graph[q.popleft()]:
                if node not in seen:
                    seen.add(node)
                    previous[node]=(edge,edge.reference["from_node"],
                                    edge.reference["to_node"])
                    q.append(node)
        self.assertIn(destination,seen,"No actual original fitted power path")
        node=destination
        while node != source:
            edge,a,b=previous[node]
            for isolator_id in edge.reference["isolator_ids"]:
                if state("isolator",isolator_id).setting!="closed":
                    set_isolator(isolator_id,"closed",operator=True)
            node=a if node==b else b

    def connect_lt(self):
        """Every existing LT branch already has its own real fitted valve."""
        for edge in CanonicalShipState.objects.filter(category="edge"):
            if edge.reference.get("network")!="lt_cooling":
                continue
            for isolator_id in edge.reference["isolator_ids"]:
                iso=state("isolator",isolator_id)
                kind=iso.reference["kind"].lower()
                position=("open" if "valve" in kind or "damper" in kind
                          else "closed")
                if iso.setting!=position:
                    set_isolator(isolator_id,position,operator=True)

    def advance(self,seconds):
        while seconds:
            dt=min(10,seconds)
            self.now+=dt
            tick_continuous_physics(now_game_time=self.now)
            seconds-=dt

    def prepare_one_hot_cabin(self):
        name="HAB-01-CAB-01-FANCOIL"
        self.power_route("NODE-LP-ROTARY-UTIL-A")
        self.power_route("NODE-PWR-"+name)
        self.connect_lt()
        configure_scenario_casualty(
            "PZ-HAB-01",operator=True,heat_kw=500)
        self.at("HAB-01-CAB-01")
        return name

    def test_original_forty_cabins_commission_only_once_and_retain_damage(self):
        self.assertEqual(commission_g19_cabin_coils(
            operator_approved=True)["fitted_units"],40)
        self.assertEqual(len(_clock().details["cabin_coils"]["units"]),40)
        name="HAB-01-CAB-01-FANCOIL"
        set_component_condition("equipment",name,"failed",operator=True)
        original=_clock().details["cabin_coils"]
        self.assertFalse(commission_g19_cabin_coils(
            operator_approved=True)["commissioned"])
        self.assertEqual(_clock().details["cabin_coils"],original)
        self.assertEqual(state("equipment",name).condition,"failed")
        self.at("HAB-01-CAB-01")
        with self.assertRaises(PhysicsError):
            self.operation(name,"on")
        self.assertEqual(self.operation(name,"off")["status"],"succeeded")

    def test_live_original_power_and_lt_valves_create_positive_cabin_output(self):
        commission_g19_cabin_coils(operator_approved=True)
        name=self.prepare_one_hot_cabin()
        self.assertEqual(self.operation(name,"on")["status"],"succeeded")
        self.advance(30)
        first=local_physics_readout(self.worker,"cabin:"+name)
        self.assertGreater(first["last_delivered_kj"],0)
        self.assertGreater(first["cumulative_delivered_kj"],0)
        self.assertEqual(first["power_endpoint"],"NODE-PWR-"+name)
        self.assertEqual(first["lt_endpoint"],"NODE-LT-HAB-01-CAB-01")
        budget=_clock().details["summary"]
        self.assertGreater(budget["cabin_cooling_kw"],0)
        self.assertLessEqual(budget["cabin_cooling_kw"],
                             budget["cabin_cooling_reserved_kw"]+1e-7)
        self.assertLessEqual(budget["cabin_cooling_reserved_kw"],
                             budget["cooling_kw"]+1e-7)
        set_isolator("ISO-PWR-"+name,"open",operator=True)
        self.advance(10)
        dark=local_physics_readout(self.worker,"cabin:"+name)
        self.assertEqual(dark["last_delivered_kj"],0)
        total=dark["cumulative_delivered_kj"]
        set_isolator("ISO-PWR-"+name,"closed",operator=True)
        set_isolator("ISO-LT-HAB-01-CAB-01","closed",operator=True)
        self.advance(10)
        cold=local_physics_readout(self.worker,"cabin:"+name)
        self.assertEqual(cold["last_delivered_kj"],0)
        self.assertEqual(cold["cumulative_delivered_kj"],total)
        set_isolator("ISO-LT-HAB-01-CAB-01","open",operator=True)
        self.advance(10)
        restored=local_physics_readout(self.worker,"cabin:"+name)
        self.assertGreater(restored["last_delivered_kj"],0)
        set_component_condition("equipment",name,"failed",operator=True)
        self.advance(10)
        stopped=local_physics_readout(self.worker,"cabin:"+name)
        self.assertEqual(stopped["last_delivered_kj"],0)

    def test_cabin_command_and_readout_never_work_remotely_or_replay(self):
        commission_g19_cabin_coils(operator_approved=True)
        name="HAB-03-CAB-02-FANCOIL"
        self.at("HAB-03-CAB-01")
        with self.assertRaises(PermissionError):
            self.operation(name,"on")
        with self.assertRaises(PermissionError):
            local_physics_readout(self.worker,"cabin:"+name)
        self.at("HAB-03-CAB-02")
        request="f"*32
        receipt=self.operation(name,"on",request)
        self.assertEqual(self.operation(name,"on",request),receipt)
        self.assertEqual(WorkReceipt.objects.filter(pk=request).count(),1)
        self.assertEqual(_clock().details["cabin_coils"]["units"][name][
            "command"],"on")
        with self.assertRaises(PermissionError):
            self.operation("HAB-07-CAB-01-FANCOIL","off",request)
        self.operation(name,"off")
        self.assertEqual(_clock().details["cabin_coils"]["units"][name][
            "command"],"off")

    def test_independent_machine_failure_is_not_an_arc_wide_thermal_reset(self):
        commission_g19_cabin_coils(operator_approved=True)
        first="HAB-01-CAB-01-FANCOIL"
        second="HAB-01-CAB-02-FANCOIL"
        self.prepare_one_hot_cabin()
        self.operation(first,"on")
        self.at("HAB-01-CAB-02")
        self.power_route("NODE-PWR-"+second)
        self.operation(second,"on")
        self.advance(30)
        ledger=_clock().details["cabin_coils"]
        self.assertGreater(ledger["units"][first]["last_kj"],0)
        self.assertGreater(ledger["units"][second]["last_kj"],0)
        other_before=ledger["units"][second]["cumulative_kj"]
        set_isolator("ISO-PWR-"+first,"open",operator=True)
        self.advance(10)
        after=_clock().details["cabin_coils"]
        self.assertEqual(after["units"][first]["last_kj"],0)
        self.assertGreater(after["units"][second]["last_kj"],0)
        self.assertGreater(after["units"][second]["cumulative_kj"],other_before)


