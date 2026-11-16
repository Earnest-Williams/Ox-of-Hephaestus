"""Integrated drum-3 control over genuine surveyed power and data."""
from evennia.utils.test_resources import EvenniaTestCase
from world.tests.test_installed_ship_network_access import NetworkAccessFixture
from world.continuous_ship_physics import _clock, verify_g19_gateway_protocol
from world.ship_control_gateway import PROFILE, translate_gateway_samples
from world.ship_dr03_authority import DrumControlError, KEY, TARGET, ROOM
from world.ship_dr03_authority_world import commission_dr03_control, local_dr03, remote_dr03
from world.ship_network_access_world import enroll_access_account
from world.full_ship_operations import state, set_component_condition
from world.ship_world import find_ship_space
from world.models import CanonicalShipEvent, CanonicalShipState, WorkReceipt

class InstalledDrumControl(NetworkAccessFixture):
    def setUp(self):
        super().setUp()
        self.tech.move_to(find_ship_space(ROOM),quiet=True)
        enroll_access_account(self.account,operator_approved=True)
        gw=_clock().details["mind_gateway"]
        samples=translate_gateway_samples(gw["last"]["raw_samples"],
            mapping_revision=gw["mapping_revision"]+1)
        confirmations={k:{"value":v["value"],"unit":v["unit"],
            "meaning":v["meaning"]} for k,v in samples.items()}
        verify_g19_gateway_protocol(operator_approved=True,profile=PROFILE,
            confirmations=confirmations,evidence_id="dr3-valve-map-checked")
        self.assertTrue(commission_dr03_control(operator_approved=True)["commissioned"])

    def test_takeover_handback_and_repeatable_conflict_receipts(self):
        before=state("isolator",TARGET).setting
        new="closed" if before=="open" else "open"
        first=remote_dr03(self.account,"1"*32,new)
        self.assertEqual(first["status"],"succeeded")
        self.assertEqual(state("isolator",TARGET).setting,new)
        self.assertEqual(remote_dr03(self.account,"1"*32,new),first)
        self.assertEqual(WorkReceipt.objects.filter(request_id="1"*32).count(),1)
        taken=local_dr03(self.tech,"2"*32,"takeover")
        self.assertTrue(taken["changed"])
        self.assertEqual(CanonicalShipState.objects.get(pk=KEY).setting,"local")
        refused=remote_dr03(self.account,"3"*32,before)
        self.assertEqual(refused["status"],"refused_local_priority")
        self.assertEqual(remote_dr03(self.account,"3"*32,before),refused)
        self.assertEqual(state("isolator",TARGET).setting,new)
        self.assertEqual(local_dr03(self.tech,"4"*32,"switch",before)["status"],"succeeded")
        self.assertEqual(state("isolator",TARGET).setting,before)
        self.assertEqual(local_dr03(self.tech,"5"*32,"handback")["status"],"succeeded")
        self.assertEqual(remote_dr03(self.account,"6"*32,new)["status"],"succeeded")
        self.assertEqual(state("isolator",TARGET).setting,new)
        self.assertEqual(CanonicalShipEvent.objects.filter(
            operation="g19_dr03_remote_switch").count(),3)

    def test_dark_backbone_preserves_crew_local_control_and_ids(self):
        local_dr03(self.tech,"7"*32,"takeover")
        for rail in ("A","B"):
            set_component_condition("edge","NET-GW-DROP-"+rail+"-DR-03",
                "severed",operator=True)
        with self.assertRaises(DrumControlError):
            remote_dr03(self.account,"8"*32,"closed")
        self.assertEqual(local_dr03(self.tech,"9"*32,"switch","open")["status"],"succeeded")
        self.assertEqual(state("isolator",TARGET).setting,"open")
        with self.assertRaises(PermissionError):
            remote_dr03(self.account,"9"*32,"open")
        self.assertEqual(local_dr03(self.tech,"a"*32,"handback")["status"],"succeeded")
        with self.assertRaises(DrumControlError):
            remote_dr03(self.account,"b"*32,"closed")
