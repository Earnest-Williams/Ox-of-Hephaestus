"""Durable, actor-authenticated social GOAP authority and receipt regressions."""
from __future__ import annotations

import base64
import json
from unittest.mock import patch

from evennia.utils.create import create_object
from evennia.utils.test_resources import EvenniaTestCase

from commands.crew import CmdOxWork
from commands.default_cmdsets import CharacterCmdSet
from commands.social import CmdOxSocialStatus
from world.models import (CrewEvent, SocialAgreement, SocialAgreementEvent,
                          SocialEvidence, WorkReceipt)
from world.social_apartment import build_apartment
from world.social_authority import agreement_summary, validate_social_arguments
from world.work_actions import execute_work, work_receipt


def ident(n):
    return f'{n:032x}'


BASE = dict(activity='hold_hands', consideration='none', scope='one_time',
            exchange_order='after')


class DurableSocialAuthorityTests(EvenniaTestCase):
    def setUp(self):
        super().setUp()
        scene = build_apartment()
        self.clara, self.ben = scene['clara'], scene['ben']
        self.outsider = create_object(
            'typeclasses.social.SocialPerson', key='Third Person',
            location=scene['room'], home=scene['room'],
        )
        self.counter = 0

    def work(self, person, operation, args, *, request_id=None):
        if request_id is None:
            self.counter += 1
            request_id = ident(self.counter)
        return execute_work(person, request_id, operation, 'social', arguments=args)

    def offer(self, terms=None, actor=None, recipient=None):
        actor = actor or self.clara
        recipient = recipient or self.ben
        response = self.work(actor, 'social_propose', {
            'recipient': recipient.dbref, 'terms': terms or BASE,
        })
        self.assertEqual(response['status'], 'succeeded', response)
        return response['agreement_id']

    def accept(self, agreement, by=None, revision=1):
        result = self.work(by or self.ben, 'social_reply', {
            'agreement_id': agreement, 'revision': revision, 'answer': 'accept',
        })
        self.assertEqual(result['status'], 'succeeded', result)
        return result

    def test_real_receipts_public_observations_and_exact_mutual_agreement(self):
        agreement = self.offer()
        self.assertEqual(agreement_summary(self.clara, agreement)['status'], 'pending')
        self.assertEqual(agreement_summary(self.outsider, agreement)['status'], 'unknown')
        before = self.work(self.clara, 'social_perform', {
            'agreement_id': agreement, 'revision': 1, 'activity': 'hold_hands',
        })
        self.assertEqual(before['status'], 'failed')
        self.accept(agreement)
        self.assertFalse(agreement_summary(self.ben, agreement)['performed'])
        rid = ident(7)
        args = {'agreement_id': agreement, 'revision': 1, 'activity': 'hold_hands'}
        done = self.work(self.clara, 'social_perform', args, request_id=rid)
        self.assertEqual(done['status'], 'succeeded', done)
        self.assertTrue(agreement_summary(self.ben, agreement)['performed'])
        first_events = SocialAgreementEvent.objects.count()
        self.assertEqual(self.work(self.clara, 'social_perform', args,
                                   request_id=rid), done)
        self.assertEqual(SocialAgreementEvent.objects.count(), first_events)
        with self.assertRaises(PermissionError):
            self.work(self.ben, 'social_perform', args, request_id=rid)
        self.assertEqual(self.work(self.ben, 'social_perform', args)['status'], 'failed')
        self.assertEqual(SocialAgreementEvent.objects.count(), 3)
        self.assertEqual(CrewEvent.objects.filter(kind='social_performed').count(), 2)
        self.assertFalse(CrewEvent.objects.filter(recipient_dbref=self.outsider.dbref).exists())
        self.assertEqual(work_receipt(self.clara, rid), done)
        self.assertEqual(work_receipt(self.ben, rid)['status'], 'unknown')

    def test_counter_requires_new_assent_and_preserves_original_promisor(self):
        agreement = self.offer()
        revised = dict(activity='hug', consideration='information',
                       scope='one_time', exchange_order='before')
        counter = self.work(self.ben, 'social_reply', {
            'agreement_id': agreement, 'revision': 1, 'answer': 'counter',
            'counter': revised,
        })
        self.assertEqual(counter['status'], 'succeeded')
        state = agreement_summary(self.clara, agreement)
        self.assertEqual(state['revision'], 2)
        self.assertEqual(state['initiator_dbref'], self.clara.dbref)
        self.assertEqual(state['recipient_dbref'], self.clara.dbref)
        self.assertEqual(self.work(self.clara, 'social_reply', {
            'agreement_id': agreement, 'revision': 1, 'answer': 'accept',
        })['status'], 'failed')
        self.accept(agreement, by=self.clara, revision=2)
        self.assertEqual(self.work(self.ben, 'social_disclose', {
            'agreement_id': agreement, 'revision': 2, 'text': 'I heard this once.',
        })['status'], 'failed')
        self.assertEqual(self.work(self.clara, 'social_perform', {
            'agreement_id': agreement, 'revision': 2, 'activity': 'hug',
        })['status'], 'failed')
        delivered = self.work(self.clara, 'social_disclose', {
            'agreement_id': agreement, 'revision': 2,
            'text': 'The notes are in the upper cabinet.',
        })
        self.assertEqual(delivered['status'], 'succeeded', delivered)
        self.assertTrue(agreement_summary(self.ben, agreement)['consideration_delivered'])
        self.assertTrue(CrewEvent.objects.filter(
            recipient_dbref=self.ben.dbref, kind='social_consideration_delivered',
            text='The notes are in the upper cabinet.',
        ).exists())
        self.assertEqual(self.work(self.clara, 'social_perform', {
            'agreement_id': agreement, 'revision': 2, 'activity': 'hug',
        })['status'], 'succeeded')
        self.assertEqual([e.revision for e in SocialAgreementEvent.objects.filter(
            agreement_id=agreement).order_by('sequence')], [1, 2, 2, 2, 2])

    def test_withdrawal_is_durable_after_payment_but_before_contact(self):
        terms = dict(BASE, consideration='information', exchange_order='before')
        agreement = self.offer(terms)
        self.accept(agreement)
        self.assertEqual(self.work(self.clara, 'social_disclose', {
            'agreement_id': agreement, 'revision': 1, 'text': 'This was delivered.',
        })['status'], 'succeeded')
        self.assertEqual(self.work(self.ben, 'social_withdraw', {
            'agreement_id': agreement, 'revision': 1,
        })['status'], 'succeeded')
        status = agreement_summary(self.clara, agreement)
        self.assertEqual(status['status'], 'withdrawn')
        self.assertTrue(status['breached'])
        self.assertTrue(status['consideration_delivered'])
        self.assertFalse(status['performed'])
        self.assertEqual(self.work(self.clara, 'social_perform', {
            'agreement_id': agreement, 'revision': 1, 'activity': 'hold_hands',
        })['status'], 'failed')
        self.assertEqual(SocialAgreement.objects.get(pk=agreement).state, 'withdrawn')

    def test_wrong_activity_absence_third_party_and_closed_replies(self):
        agreement = self.offer()
        self.accept(agreement)
        with self.assertRaises(ValueError):
            self.work(self.clara, 'social_perform', {
                'agreement_id': agreement, 'revision': 1, 'activity': 'sit_together ',
            })
        # Unauthorized access refuses without revealing another's private terms.
        with self.assertRaises(PermissionError):
            self.work(self.outsider, 'social_withdraw', {
                'agreement_id': agreement, 'revision': 1,
            })
        self.ben.move_to(create_object(
            'typeclasses.social.SocialRoom', key='Different Room', nohome=True),
            quiet=True)
        self.assertEqual(self.work(self.clara, 'social_perform', {
            'agreement_id': agreement, 'revision': 1, 'activity': 'hold_hands',
        })['status'], 'failed')
        self.assertFalse(agreement_summary(self.ben, agreement)['performed'])

    def test_typed_payload_rejects_fake_authorization(self):
        with self.assertRaises(ValueError):
            validate_social_arguments('social_perform', {
                'agreement_id': ident(55), 'revision': 1,
                'activity': 'kiss', 'world_verified': True,
            })
        with self.assertRaises(ValueError):
            validate_social_arguments('social_propose', {
                'recipient': self.ben.dbref,
                'terms': dict(BASE, consideration='payment'),
            })
        with self.assertRaises(ValueError):
            validate_social_arguments('social_propose', {
                'recipient': self.ben.dbref,
                'terms': dict(BASE, consideration='resource',
                              consideration_evidence={'target': 'social', 'operation': 'social_perform'}),
            })

    def test_expiration_reopens_pair_without_rewriting_first_offer(self):
        with patch('world.social_authority._now', return_value=100.0):
            old = self.offer()
        with patch('world.social_authority._now', return_value=999.0):
            replacement = self.offer()
        self.assertNotEqual(old, replacement)
        self.assertEqual(SocialAgreement.objects.get(pk=old).state, 'expired')
        self.assertEqual(SocialAgreement.objects.get(pk=replacement).state, 'pending')
        self.assertEqual(SocialAgreementEvent.objects.filter(
            agreement_id=old, kind='expired').count(), 1)

    def test_journal_write_failure_cannot_leave_unreceipted_offer(self):
        with patch('world.social_authority.emit', side_effect=RuntimeError('journal down')):
            with self.assertRaises(RuntimeError):
                self.work(self.clara, 'social_propose', {
                    'recipient': self.ben.dbref, 'terms': BASE,
                }, request_id=ident(98))
        self.assertFalse(SocialAgreement.objects.filter(pk=ident(98)).exists())
        self.assertFalse(WorkReceipt.objects.filter(pk=ident(98)).exists())
        self.assertEqual(self.work(self.clara, 'social_propose', {
            'recipient': self.ben.dbref, 'terms': BASE,
        }, request_id=ident(98))['status'], 'succeeded')

    def test_work_evidence_requires_actual_matching_success_and_cannot_reuse(self):
        from world.bootstrap import build_ship
        ship = build_ship()
        ari, iona = ship['watch'], ship['chief']
        terms = dict(BASE, activity='practical_help',
                     activity_evidence={'target': 'pump', 'operation': 'isolate'})
        agreement = self.offer(terms, actor=ari, recipient=iona)
        self.accept(agreement, by=iona)
        self.assertFalse(agreement_summary(ari, agreement)['performed'])
        invalid = self.work(ari, 'social_evidence', {
            'agreement_id': agreement, 'revision': 1,
            'side': 'activity', 'work_request_id': ident(90),
        })
        self.assertEqual(invalid['status'], 'failed')
        ok, reason = ship['pump'].inject_fault()
        self.assertTrue(ok, reason)
        work_id = ident(91)
        result = execute_work(ari, work_id, 'isolate', 'pump')
        self.assertEqual(result['status'], 'succeeded', result)
        confirmed = self.work(ari, 'social_evidence', {
            'agreement_id': agreement, 'revision': 1,
            'side': 'activity', 'work_request_id': work_id,
        })
        self.assertEqual(confirmed['status'], 'succeeded', confirmed)
        self.assertEqual(SocialEvidence.objects.count(), 1)
        self.assertTrue(agreement_summary(iona, agreement)['performed'])
        self.assertNotEqual(work_id, confirmed['request_id'])
        self.assertEqual(self.work(ari, 'social_evidence', {
            'agreement_id': agreement, 'revision': 1,
            'side': 'activity', 'work_request_id': work_id,
        })['status'], 'failed')

    def test_commands_are_character_authenticated_and_return_private_oob(self):
        cmdset = CharacterCmdSet()
        cmdset.at_cmdset_creation()
        self.assertIn('oxsocialstatus', {command.key for command in cmdset.commands})
        arguments = {'recipient': self.ben.dbref, 'terms': BASE}
        token = base64.urlsafe_b64encode(json.dumps(arguments).encode()).decode().rstrip('=')
        cmd = CmdOxWork()
        cmd.caller = self.clara
        cmd.args = ident(71) + ' social_propose social ' + token
        with patch.object(self.clara, 'msg') as reply:
            cmd.func()
            payload = [c.kwargs['ox_receipt'][0][0] for c in reply.call_args_list
                       if 'ox_receipt' in c.kwargs]
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]['status'], 'succeeded', payload)
        summary = CmdOxSocialStatus()
        summary.caller = self.ben
        summary.args = ident(71)
        with patch.object(self.ben, 'msg') as outgoing:
            summary.func()
            data = outgoing.call_args.kwargs['ox_social_status'][0][0]
            self.assertEqual(data['status'], 'pending')
            self.assertEqual(data['activity'], 'hold_hands')