"""Contract-only regressions: no Evennia installation or API is implied."""
import copy
import unittest
from pydantic import ValidationError
from ox_contracts.world_read_model import parse_world_read_page, ModelIdentity

def base(scope="developer_actual"):
    return dict(schema_version="ox.world.read/1", world_id="OX-FULL-SHIP",
                models=dict(topology_version="0.4", engineering_version="0.5-candidate"),
                publication_seq=17, game_time_s=1020.0,
                page=dict(complete=True), scope=scope)

def actual():
    return {**base(), "equipment": [
        dict(equipment_id="GEN-B", space_id="ENG-CONTROL", condition="serviceable",
             measurements=[dict(name="power_kw", unit="kW", value=200.0)])],
        "stocks": [
            dict(account_id="INV-REACTION", custodian="inventory",
                 accounting="legacy_reference", quantity_kg=10000.0),
            dict(account_id="motion.propellant_kg", custodian="motion_ledger",
                 accounting="operational_balance", quantity_kg=9500.0)],
        "audit_events": [dict(event_id="PHY:17", kind="hull_alarm",
                              occurred_game_s=1000.0, visibility="developer_only")]}

def observed():
    return {**base("actor_observed"), "character_id":"#57", "location_id":"ENG-CONTROL",
       "equipment":[dict(equipment_id="GEN-B", availability="stale",
                         reported_condition="serviceable",
                         evidence=dict(source="local_panel", source_id="LP-ENG",
                                       observed_game_s=990.0))],
       "exits":[dict(link_id="ACC-ENG-HAB",from_space_id="ENG-CONTROL",
                     assessment="unknown",
                     evidence=dict(source="local_capability", source_id="ACC-ENG-HAB",
                                   observed_game_s=1019.0))],
       "addressed_events":[dict(event_id="ALARM:18",recipient_character_id="#57",
                                kind="life_support_warning",occurred_game_s=1018.0,
                                source="delivered_world_event")]}

class WorldReadContractTests(unittest.TestCase):
    def bad(self, data):
        with self.assertRaises((ValidationError, ValueError)):
            parse_world_read_page(data)

    def test_strict_roundtrips_and_scope(self):
        for payload in (actual(), observed()):
            model = parse_world_read_page(payload)
            self.assertEqual(model.scope, payload["scope"])
            self.assertEqual(type(model).model_validate_json(model.model_dump_json()),model)

    def test_schema_and_corrupt_measurement(self):
        for field, value in (("schema_version","ox.world.read/2"),
                             ("scope","operator"),("game_time_s",float("nan")),
                             ("publication_seq",-1)):
            payload=actual()
            payload[field]=value
            self.bad(payload)
        payload=actual()
        payload["equipment"][0]["measurements"][0]["value"]=float("inf")
        self.bad(payload)
        payload=actual()
        payload["handler_memory"]={}
        self.bad(payload)

    def test_legacy_fuel_is_not_spendable(self):
        self.assertEqual(len(parse_world_read_page(actual()).stocks),2)
        for fuel in ("INV-REACTION","INV-FTL-FUEL"):
            p=actual()
            p["stocks"][0]["account_id"]=fuel
            p["stocks"][0]["accounting"]="operational_balance"
            self.bad(p)
        p=actual()
        p["stocks"][1]["account_id"]="motion.dry_mass_kg"
        self.bad(p)
        p=actual()
        p["stocks"][1]["quantity_kg"]=float("inf")
        self.bad(p)

    def test_actor_privacy_and_observation_freshness(self):
        for mutate in (
            lambda p:p["addressed_events"][0].update(recipient_character_id="#58"),
            lambda p:p.update(audit_events=actual()["audit_events"]),
            lambda p:p["exits"][0].update(from_space_id="CMD-PRIMARY"),
            lambda p:p["exits"][0]["evidence"].update(source="direct_inspection"),
            lambda p:p["equipment"][0]["evidence"].update(observed_game_s=99999.0),
            lambda p:p["equipment"][0].update(availability="unavailable"),
            lambda p:p["equipment"][0]["evidence"].update(source="addressed_event"),
        ):
            p=observed()
            mutate(p)
            self.bad(p)
        p=observed()
        p["equipment"][0].update(availability="unavailable",reported_condition=None)
        parse_world_read_page(p)

    def test_pagination_duplicates_and_future(self):
        for changes in (dict(complete=False),dict(complete=True,next_cursor="abc")):
            p=actual()
            p["page"]=changes
            self.bad(p)
        p=actual()
        p["page"]=dict(complete=False,next_cursor="abc")
        parse_world_read_page(p)
        p=actual()
        p["stocks"].append(copy.deepcopy(p["stocks"][0]))
        self.bad(p)
        p=actual()
        p["audit_events"][0]["occurred_game_s"]=2000.0
        self.bad(p)
        p=actual()
        p["equipment"]=p["equipment"]*129
        self.bad(p)

    def test_renderer_requires_both_model_identities(self):
        model=ModelIdentity.model_validate(base()["models"])
        model.require_renderer(topology_version="0.4",engineering_version="0.5-candidate")
        for topology,engineering in (("0.4","0.4"),("0.5","0.5-candidate")):
            with self.assertRaises(ValueError):
                model.require_renderer(topology_version=topology,engineering_version=engineering)

if __name__=="__main__":
    unittest.main()
