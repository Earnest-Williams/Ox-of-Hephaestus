"""G7b targeted tests: reusable bargaining, private motives and GOAP choices."""
import unittest

from ox_ai.planning.goap import GoapPlanner
from ox_ai.social.contracts import ContractBoard, Terms
from ox_ai.social.domain import SOCIAL_OPERATORS, ACTION_BY_NAME
from ox_ai.scenarios.apartment_extended import (
    ApartmentExpanded, SocialGoapMind, Disposition, make_pair, run_offline,
)


class ReusableSocialOperatorsTests(unittest.TestCase):
    def test_broad_catalog_is_independent_of_room_and_profession(self):
        self.assertGreaterEqual(len(SOCIAL_OPERATORS), 70)
        self.assertEqual(len({a.name for a in SOCIAL_OPERATORS}), len(SOCIAL_OPERATORS))
        self.assertTrue({'emotion','boundary','bargain','cooperation','proximity','contact'} <= {a.category for a in SOCIAL_OPERATORS})
        self.assertTrue({'express_uncertainty','state_boundary','accept_terms',
                         'withdraw_agreement','offer_concession','coordinate_work',
                         'kiss','hug','hold_hands'} <= set(ACTION_BY_NAME))

    def test_actual_goap_search_finds_social_intermediate_steps(self):
        model = GoapPlanner([a.goap() for a in SOCIAL_OPERATORS])
        plan = model.plan({'together'}, {'affection_expressed'})
        self.assertEqual([a.name for a in plan.actions],
                         ['express_appreciation','express_affection'])
        self.assertGreater(plan.expanded_states,0)
        with self.assertRaises(Exception):
            model.plan({'together'}, {'held_hands'})


class NegotiationBoardTests(unittest.TestCase):
    def setUp(self):
        self.board = ContractBoard(ttl=4)
        self.base = Terms('hold_hands')

    def test_offer_does_not_mean_acceptance_or_authorize_touch(self):
        offer = self.board.propose('Clara','Ben',self.base)
        self.assertEqual(self.board.offers[offer.offer_id].state,'pending')
        with self.assertRaises(PermissionError):
            self.board.perform('Clara',offer.offer_id,1,'hold_hands','r1',parties_colocated=True)
        with self.assertRaises(PermissionError):
            self.board.reply('Eve',offer.offer_id,1,'accept')
        with self.assertRaises(PermissionError):
            self.board.reply('Clara',offer.offer_id,1,'accept')

    def test_counteroffer_is_real_revision_and_requires_new_assent(self):
        o=self.board.propose('Clara','Ben',Terms('kiss'))
        counter=Terms('hold_hands','information','limited','before')
        self.board.reply('Ben',o.offer_id,1,'counter',counter=counter)
        self.assertEqual(self.board.offers[o.offer_id].revision,2)
        self.assertEqual(self.board.offers[o.offer_id].initiator,'Clara')
        with self.assertRaises(ValueError):
            self.board.reply('Ben',o.offer_id,1,'accept')
        with self.assertRaises(ValueError):
            self.board.reply('Clara',o.offer_id,1,'counter',counter=counter)
        self.board.reply('Clara',o.offer_id,2,'accept')
        self.assertEqual(set(self.board.offers[o.offer_id].accepted_by),{'Clara','Ben'})
        with self.assertRaises(PermissionError):
            self.board.perform('Ben',o.offer_id,2,'hold_hands','r2',parties_colocated=True)
        with self.assertRaises(PermissionError):
            self.board.deliver_consideration('Ben',o.offer_id,2,'bad',world_verified=True)
        with self.assertRaises(PermissionError):
            self.board.deliver_consideration('Clara',o.offer_id,2,'bad',world_verified=False)
        delivered=self.board.deliver_consideration('Clara',o.offer_id,2,'proof',world_verified=True)
        self.assertEqual(delivered.kind,'consideration_delivered')
        done=self.board.perform('Ben',o.offer_id,2,'hold_hands','touch',parties_colocated=True)
        self.assertEqual(done.kind,'performed')
        self.assertEqual(self.board.perform('Ben',o.offer_id,2,'hold_hands','touch',parties_colocated=True),done)
        with self.assertRaises(ValueError):
            self.board.perform('Clara',o.offer_id,2,'hold_hands','touch',parties_colocated=True)

    def test_expiry_defer_decline_and_revocation(self):
        a=self.board.propose('Clara','Ben',self.base)
        self.board.turn=5
        with self.assertRaises(ValueError):
            self.board.reply('Ben',a.offer_id,1,'accept')
        self.assertEqual(self.board.offers[a.offer_id].state,'expired')
        b=self.board.propose('Clara','Ben',self.base)
        self.board.reply('Ben',b.offer_id,1,'defer')
        self.assertEqual(self.board.offers[b.offer_id].state,'deferred')
        c=self.board.propose('Clara','Ben',self.base)
        self.board.reply('Ben',c.offer_id,1,'accept')
        self.board.withdraw('Ben',c.offer_id,1)
        with self.assertRaises(PermissionError):
            self.board.perform('Clara',c.offer_id,1,'hold_hands','r3',parties_colocated=True)

    def test_co_location_and_cross_activity_guards(self):
        o=self.board.propose('Clara','Ben',self.base)
        self.board.reply('Ben',o.offer_id,1,'accept')
        with self.assertRaises(PermissionError):
            self.board.perform('Clara',o.offer_id,1,'hug','q1',parties_colocated=True)
        with self.assertRaises(PermissionError):
            self.board.perform('Clara',o.offer_id,1,'hold_hands','q2',parties_colocated=False)
        self.assertIsNone(self.board.offers[o.offer_id].performed_by)

    def test_nonphysical_bargains_are_commitments_not_automatic_work(self):
        o=self.board.propose('Ari','Mara',Terms('shift_swap','help','later'))
        self.board.reply('Mara',o.offer_id,1,'accept')
        self.assertIsNone(self.board.offers[o.offer_id].performed_by)
        self.assertIsNone(self.board.offers[o.offer_id].consideration_delivered_by)
        with self.assertRaises(ValueError):
            self.board.propose('Ari','Mara',Terms('unknown'))


class ExpandedScenarioTests(unittest.TestCase):
    def test_two_independent_minds_complete_mutual_exchange(self):
        r=run_offline(variant='mutual')
        self.assertEqual(r['status'],'complete')
        self.assertEqual(r['model_calls'],0)
        poses=[t for t in r['trace'] if t['action']=='perform_agreement']
        self.assertTrue(poses,r)
        for pose in poses:
            offer=next(o for o in r['offers'] if o['id']==pose['offer_id'])
            self.assertEqual(offer['state'],'accepted')
            self.assertEqual(offer['performed'],pose['speaker'])
        self.assertGreater(r['planning_calls']['Ben'],0)
        self.assertGreater(r['planning_calls']['Clara'],0)

    def test_cautious_person_can_counter_and_express_hesitation(self):
        r=run_offline(variant='cautious')
        a=[t['action'] for t in r['trace']]
        self.assertIn('express_uncertainty',a)
        self.assertIn('respond_counter',a)
        self.assertIn('state_preference',a)
        self.assertIn('acknowledge_boundary',a)
        self.assertEqual(r['status'],'complete')

    def test_bargained_intimacy_does_not_imply_personal_attraction(self):
        r=run_offline(variant='instrumental')
        self.assertEqual(r['status'],'complete')
        ben=r['private_final_state']['Ben']
        self.assertLess(ben['disposition']['affection'],30)
        p=next(o for o in r['offers'] if o['activity']=='hold_hands')
        self.assertEqual(p['consideration'],'information')
        self.assertEqual(p['exchange_order'],'before')
        self.assertEqual(p['delivered'],'Clara')
        self.assertEqual(p['performed'],'Ben')
        self.assertEqual(p['state'],'accepted')
        self.assertTrue(any(t['private_motivation'].endswith('instrumental')
                            for t in r['trace'] if t['speaker']=='Ben'))
        order=[t['kind'] for t in r['trace'] if t['offer_id']==p['id']]
        self.assertLess(order.index('consideration_delivered'),order.index('performed'))

    def test_decline_closes_off_future_solicitations(self):
        r=run_offline(variant='mismatch')
        self.assertEqual(r['status'],'complete')
        self.assertEqual([o['state'] for o in r['offers']],['declined'])
        self.assertFalse(any(t['action']=='perform_agreement' for t in r['trace']))

    def test_duty_or_expectation_can_motivate_agreement_not_desire(self):
        r=run_offline(variant='obligation')
        self.assertEqual(r['status'],'complete')
        self.assertIn('accepted',[o['state'] for o in r['offers']])
        self.assertEqual(r['private_final_state']['Ben']['disposition']['affection'],20)

    def test_same_bargaining_primitives_work_without_romance(self):
        r=run_offline(variant='work_trade')
        self.assertEqual(r['status'],'complete')
        self.assertTrue(any(o['activity']=='shift_swap' and o['state']=='accepted' for o in r['offers']))
        self.assertTrue(all(t['action']!='perform_agreement' for t in r['trace']))
        self.assertTrue(all(o['performed'] is None for o in r['offers']))

    def test_updated_private_preferences_allow_revoking_before_touch(self):
        r=run_offline(variant='reconsider')
        self.assertEqual(r['status'],'complete')
        self.assertIn('withdrawn',[o['state'] for o in r['offers']])
        self.assertFalse(any(t['kind']=='performed' for t in r['trace']))
        self.assertGreaterEqual(r['private_final_state']['Clara']['emotions']['resentment'],75)

    def test_cap_and_no_predicted_world_success(self):
        r=run_offline(variant='mutual',turn_cap=1)
        self.assertEqual(r['status'],'turn_capped')
        self.assertEqual(r['turns'],1)
        self.assertFalse(r['offers'])
        a,b=make_pair('mutual')
        proposal=a.propose()
        self.assertNotIn('warmth_expressed',a.beliefs)
        self.assertEqual(a.model_calls,0)
        with self.assertRaises(PermissionError):
            a.confirmed(b.propose())
        self.assertNotIn('warmth_expressed',a.beliefs)


if __name__=='__main__':
    unittest.main()
