"""Authoritative, durable bilateral negotiations for ordinary Evennia characters.

No AI handler, private emotion, or simulated contract board can mutate these
records. Every write is entered via execute_work(target='social'), uses the
existing globally idempotent WorkReceipt namespace, and is serialized by
locked Django rows. Event notifications are addressed to the two parties.
"""
from __future__ import annotations

import re
import hashlib
from collections.abc import Mapping

from django.db import transaction
from evennia.objects.models import ObjectDB
from evennia.utils import gametime

from world.event_journal import emit
from world.models import SocialAgreement, SocialAgreementEvent, SocialEvidence, WorkReceipt

# These are the same public vocabulary as the independent GOAP handler. All
# authority and validation below is local to Evennia, not imported from AI.
ACTIVITIES = frozenset({
    'another_date', 'stay_longer', 'stay_overnight', 'sit_together',
    'move_closer', 'hold_hands', 'cuddle', 'hug', 'kiss', 'private_intimacy',
    'quiet_company', 'walk_together', 'talk_privately', 'share_secret',
    'provide_information', 'offer_introduction', 'practical_help',
    'shift_swap', 'lend_equipment', 'share_supplies', 'assist_task',
    'joint_investigation', 'protect_reputation', 'keep_confidence',
    'share_meal', 'exchange_contact', 'emotional_support', 'lend_money',
    'give_transport', 'provide_shelter', 'exchange_funds', 'contract_work',
    'public_endorsement', 'share_credit', 'meet_friends', 'future_commitment',
})
CONSIDERATIONS = frozenset({
    'none', 'extra_time', 'help', 'information', 'future_favor',
    'confidentiality', 'shared_risk', 'resource', 'introduction',
    'payment', 'shelter', 'transport', 'protection', 'public_credit',
})
SCOPES = frozenset({'one_time', 'tonight', 'later', 'limited', 'ongoing'})
ORDERS = frozenset({'before', 'after', 'simultaneous'})
PHYSICAL = frozenset({
    'sit_together', 'move_closer', 'hold_hands', 'hug', 'cuddle', 'kiss',
    'private_intimacy', 'walk_together',
})
# Only actions with a separately checkable world work receipt may be marked
# fulfilled by evidence; a vague promise of overtime is not completed by text.
WORK_CONSIDERATIONS = frozenset({'help', 'future_favor'})
WORK_ACTIVITIES = frozenset({
    'practical_help', 'shift_swap', 'assist_task', 'joint_investigation',
    'contract_work',
})
REQUEST_ID = re.compile(r'[0-9a-f]{32}\Z')
DBREF = re.compile(r'#[1-9][0-9]*\Z')
SAFE_TEXT = re.compile(r'[^\x00-\x1f\x7f]{1,200}\Z')
OPERATIONS = frozenset({
    'social_propose', 'social_reply', 'social_withdraw', 'social_perform',
    'social_disclose', 'social_evidence',
})


def _id(value):
    if not isinstance(value, str) or REQUEST_ID.fullmatch(value) is None:
        raise ValueError('Expected a stable lowercase 32-hex identity')
    return value


def _ref(value):
    if not isinstance(value, str) or DBREF.fullmatch(value) is None:
        raise ValueError('Expected a real Evennia dbref')
    return value


def _mapping(value):
    if not isinstance(value, Mapping):
        raise ValueError('Typed social arguments required')
    return dict(value)


def _work_spec(value):
    spec = _mapping(value)
    if set(spec) != {'target', 'operation'}:
        raise ValueError('Work evidence requires target and operation')
    target, operation = spec['target'], spec['operation']
    # No self-proving social work, client-written service receipt or arbitrary
    # textual claim can ever count as world-completed task performance.
    allowed = {
        'pump': {'isolate', 'repair', 'commission'},
        'cargo': {'restow', 'certify', 'retension'},
        'scrubber': {'isolate', 'replace', 'restart', 'purge'},
        'inventory': {'accept_supply', 'collect_supply', 'deliver_supply'},
        'ship': {'radio', 'request', 'approve', 'resolve', 'offer', 'accept',
                 'anomaly_report', 'anomaly_probe_report', 'anomaly_assess'},
    }
    if not isinstance(target, str) or not isinstance(operation, str):
        raise ValueError('Malformed work evidence')
    if operation not in allowed.get(target, frozenset()):
        raise ValueError('Evidence must name a supported, real world operation')
    return {'target': target, 'operation': operation}


def _terms(value):
    data = _mapping(value)
    expected = {'activity', 'consideration', 'scope', 'exchange_order'}
    optional = {'activity_evidence', 'consideration_evidence'}
    if not expected.issubset(data) or set(data) - (expected | optional):
        raise ValueError('Exact typed social terms required')
    for key, domain in (('activity', ACTIVITIES), ('consideration', CONSIDERATIONS),
                        ('scope', SCOPES), ('exchange_order', ORDERS)):
        if not isinstance(data[key], str) or data[key] not in domain:
            raise ValueError('Unknown social term: ' + key)
    if data['consideration'] == 'none' and data['exchange_order'] != 'after':
        raise ValueError('No consideration can precede an act')
    if data['exchange_order'] == 'simultaneous':
        # Separate work receipts are not an atomic exchange of consideration
        # and performance. Do not promise a guarantee the world cannot make.
        raise ValueError('Atomic simultaneous exchange is not implemented')
    if data['consideration'] == 'none' and 'consideration_evidence' in data:
        raise ValueError('No phantom consideration evidence')
    if data['consideration'] != 'none':
        if data['consideration'] in WORK_CONSIDERATIONS:
            if 'consideration_evidence' not in data:
                raise ValueError('Work concession must identify a verifiable task')
            data['consideration_evidence'] = _work_spec(data['consideration_evidence'])
        elif data['consideration'] == 'information':
            if 'consideration_evidence' in data:
                raise ValueError('Disclosures are verified by addressed delivery')
        else:
            # No means exists yet to transfer cash, property or a reputation.
            # These can be proposed as private GOAP possibilities but cannot
            # become falsely verified obligations in the actual game.
            raise ValueError('No world-owned fulfillment path for this concession')
    if data['activity'] in WORK_ACTIVITIES:
        if 'activity_evidence' not in data:
            raise ValueError('Work activity must specify the actual world task')
        data['activity_evidence'] = _work_spec(data['activity_evidence'])
        if (data['activity'] == 'shift_swap'
                and data['activity_evidence'] != {'target': 'ship', 'operation': 'accept'}):
            raise ValueError('A shift swap requires an actual world watch-handover receipt')
        if (data['activity'] == 'joint_investigation'
                and data['activity_evidence']['operation'] not in {
                    'anomaly_report', 'anomaly_probe_report', 'anomaly_assess',
                }):
            raise ValueError('Investigation requires a world investigative work receipt')
    elif 'activity_evidence' in data:
        raise ValueError('Non-work activities cannot use unrelated work receipts')
    return data


def validate_social_arguments(operation: str, arguments: Mapping | None) -> dict:
    """Reject undeclared payload fields, fake receipts, and arbitrary verbs."""
    if operation not in OPERATIONS:
        raise ValueError('Unknown social command')
    a = _mapping(arguments)
    if operation == 'social_propose':
        if set(a) != {'recipient', 'terms'}:
            raise ValueError('Proposal requires one recipient and exact terms')
        return {'recipient': _ref(a['recipient']), 'terms': _terms(a['terms'])}
    if operation == 'social_reply':
        necessary = {'agreement_id', 'revision', 'answer'}
        if not necessary.issubset(a) or set(a) - (necessary | {'counter'}):
            raise ValueError('Malformed addressed reply')
        if a['answer'] not in ('accept', 'decline', 'defer', 'counter'):
            raise ValueError('Unknown reply')
        if (a['answer'] == 'counter') != ('counter' in a):
            raise ValueError('A counter requires changed, complete typed terms')
        result = {'agreement_id': _id(a['agreement_id']),
                  'revision': _revision(a['revision']), 'answer': a['answer']}
        if 'counter' in a:
            result['counter'] = _terms(a['counter'])
        return result
    necessary = {'agreement_id', 'revision'}
    additional = ({'activity'} if operation == 'social_perform' else
                  {'text'} if operation == 'social_disclose' else
                  {'side', 'work_request_id'} if operation == 'social_evidence' else set())
    if set(a) != necessary | additional:
        raise ValueError('Malformed typed agreement operation')
    result = {'agreement_id': _id(a['agreement_id']),
              'revision': _revision(a['revision'])}
    if operation == 'social_perform':
        if a['activity'] not in PHYSICAL:
            raise ValueError('Only world-supported local physical acts may use perform')
        result['activity'] = a['activity']
    if operation == 'social_disclose':
        if not isinstance(a['text'], str) or SAFE_TEXT.fullmatch(a['text']) is None:
            raise ValueError('Information delivery must be bounded printable text')
        result['text'] = a['text']
    if operation == 'social_evidence':
        if a['side'] not in ('activity', 'consideration'):
            raise ValueError('Unknown evidence obligation side')
        result.update(side=a['side'], work_request_id=_id(a['work_request_id']))
    return result


def _revision(value):
    if type(value) is not int or not 1 <= value <= 100:
        raise ValueError('Bounded exact agreement revision required')
    return value


def _participant(dbref):
    from evennia.objects.objects import DefaultCharacter
    obj = ObjectDB.objects.filter(pk=int(_ref(dbref)[1:])).first()
    if obj is None or not isinstance(obj, DefaultCharacter):
        raise PermissionError('Only an existing character may receive social offers')
    if obj.db.ox_terminal_dead:
        raise PermissionError('Cannot contract with a deceased character')
    return obj


def _colocated(first, second):
    return bool(first.location is not None and first.location == second.location)


def _now():
    return float(gametime.gametime(absolute=True))


def _pair(a, b):
    return ':'.join(sorted((a, b)))


def _load_locked(actor, agreement_id, revision):
    agreement = SocialAgreement.objects.select_for_update().filter(pk=agreement_id).first()
    if agreement is None:
        raise PermissionError('No addressed agreement')
    if actor.dbref not in (agreement.first_dbref, agreement.second_dbref):
        # Do not tell an uninvolved person whether the agreement exists.
        raise PermissionError('No addressed agreement')
    if agreement.revision != revision:
        raise ValueError('Stale agreement revision')
    return agreement


def _other(agreement, actor):
    return _participant(agreement.second_dbref if actor.dbref == agreement.first_dbref
                        else agreement.first_dbref)


def _record(agreement, actor, kind, request_id, *, text=''):
    """One atomic event history row plus separate addressed durable observations."""
    entry = SocialAgreementEvent.objects.create(
        agreement=agreement, request_id=request_id,
        actor_dbref=actor.dbref, kind=kind, revision=agreement.revision,
        terms=dict(agreement.terms), state=agreement.state, game_time=_now(),
    )
    extra = {'agreement_id': agreement.agreement_id, 'revision': agreement.revision,
             'activity': agreement.terms['activity'], 'consideration': agreement.terms['consideration'],
             'scope': agreement.terms['scope'], 'exchange_order': agreement.terms['exchange_order'],
             'state': agreement.state, 'history_id': entry.pk}
    counterpart = _other(agreement, actor)
    # World-authored summary when the step carries no spoken content.
    text = text or ('Agreement %s %s (revision %d).'
                    % (agreement.agreement_id, kind.replace('_', ' '),
                       agreement.revision))
    first = emit(None, actor, 'social_' + kind, sender=actor, data=extra, text=text)
    emit(None, counterpart, 'social_' + kind, sender=actor, data=extra, text=text)
    return first['event_id']


def _pending_expiration(agreement, actor, request_id):
    if agreement.state == 'pending' and _now() > agreement.expires_at:
        agreement.state = 'expired'
        agreement.save(update_fields=['state'])
        _record(agreement, actor, 'expired', request_id)
        return True
    return False


def _reject(reason):
    return False, reason, None, None


def apply_social_action(actor, request_id: str, operation: str, a: dict):
    """Called inside the common WorkReceipt transaction, after actor lock.

    Outcome: (success, reason, source_event_id, agreement); never guess success.
    A refused operation cannot mutate an unrelated person or manufacture a
    concession. All writes to this row use select_for_update.
    """
    if actor.db.ox_terminal_dead:
        return _reject('deceased_character')
    if operation == 'social_propose':
        recipient = _participant(a['recipient'])
        if recipient.pk == actor.pk or not _colocated(actor, recipient):
            return _reject('requires_another_colocated_person')
        pair_key = _pair(actor.dbref, recipient.dbref)
        for previous in SocialAgreement.objects.select_for_update().filter(
                pair_key=pair_key, state='pending'):
            if previous.expires_at >= _now():
                return _reject('pending_offer_exists')
            previous.state = 'expired'
            previous.save(update_fields=['state'])
            expiry_request = hashlib.sha256(
                ('social-expired-' + previous.agreement_id).encode('ascii')
            ).hexdigest()[:32]
            _record(previous, actor, 'expired', expiry_request)
        # Pending identity is also enforced through a database partial unique
        # constraint; concurrent opposing proposals cannot both be accepted.
        agreement = SocialAgreement.objects.create(
            agreement_id=request_id, pair_key=pair_key,
            first_dbref=actor.dbref, second_dbref=recipient.dbref,
            proposer_dbref=actor.dbref, recipient_dbref=recipient.dbref,
            initiator_dbref=actor.dbref, terms=a['terms'], state='pending',
            revision=1, opened_at=_now(), expires_at=_now() + 600,
        )
        event_id = _record(agreement, actor, 'proposed', request_id)
        return True, 'proposed', event_id, agreement

    agreement = _load_locked(actor, a['agreement_id'], a['revision'])
    if _pending_expiration(agreement, actor, request_id):
        return False, 'offer_expired', None, agreement
    if operation == 'social_reply':
        if agreement.state != 'pending' or actor.dbref != agreement.recipient_dbref:
            return _reject('not_addressed_pending_offer')
        reply = a['answer']
        if reply == 'counter':
            terms = a['counter']
            if terms == agreement.terms or agreement.revision >= 100:
                return _reject('counter_requires_different_terms')
            agreement.terms = terms
            agreement.revision += 1
            agreement.proposer_dbref, agreement.recipient_dbref = (
                agreement.recipient_dbref, agreement.proposer_dbref)
            agreement.opened_at = _now()
            agreement.expires_at = agreement.opened_at + 600
            kind = 'countered'
        elif reply == 'accept':
            agreement.state = 'accepted'
            agreement.accepted_at = _now()
            kind = 'accepted'
        else:
            agreement.state = 'declined' if reply == 'decline' else 'deferred'
            kind = agreement.state
        agreement.save()
        return True, kind, _record(agreement, actor, kind, request_id), agreement

    if operation == 'social_withdraw':
        if agreement.state not in ('pending', 'accepted') or agreement.performance_id:
            return _reject('cannot_withdraw_completed_or_closed_terms')
        # Voluntarily revoking a not-yet-performed physical agreement always
        # remains possible. Previously delivered consideration stays recorded.
        agreement.state = 'withdrawn'
        agreement.breached = bool(agreement.consideration_id)
        agreement.save(update_fields=['state', 'breached'])
        return True, 'withdrawn', _record(agreement, actor, 'withdrawn', request_id), agreement

    if agreement.state != 'accepted':
        return _reject('exact_active_acceptance_required')
    if operation == 'social_disclose':
        if agreement.terms['consideration'] != 'information':
            return _reject('no_information_consideration_promised')
        if actor.dbref != agreement.initiator_dbref or agreement.consideration_id:
            return _reject('not_outstanding_initiator_disclosure')
        # This proves *delivery of a statement*, not its accuracy or usefulness.
        counterpart = _other(agreement, actor)
        if not _colocated(actor, counterpart):
            return _reject('disclosure_requires_colocation')
        agreement.consideration_id = request_id
        agreement.save(update_fields=['consideration_id'])
        event_id = _record(agreement, actor, 'consideration_delivered', request_id,
                           text=a['text'])
        return True, 'information_transmitted_not_verified_true', event_id, agreement

    if operation == 'social_evidence':
        side = a['side']
        obligation = 'consideration' if side == 'consideration' else 'activity'
        column = 'consideration_id' if side == 'consideration' else 'performance_id'
        existing = getattr(agreement, column)
        if existing:
            return _reject('obligation_already_fulfilled')
        spec = agreement.terms.get(obligation + '_evidence')
        if not isinstance(spec, dict):
            return _reject('no_grounded_work_evidence_in_terms')
        if (side == 'consideration' and actor.dbref != agreement.initiator_dbref):
            return _reject('only_promising_party_may_claim_concession')
        evidence = WorkReceipt.objects.select_for_update().filter(
            pk=a['work_request_id'], actor_dbref=actor.dbref,
            target=spec['target'], operation=spec['operation'],
        ).first()
        if (evidence is None or evidence.outcome.get('status') != 'succeeded'
                or evidence.game_time < agreement.accepted_at
                or SocialEvidence.objects.filter(receipt=evidence).exists()):
            return _reject('no_unused_matching_world_work_receipt')
        if (side == 'activity' and agreement.terms['consideration'] != 'none'
                and agreement.terms['exchange_order'] == 'before'
                and agreement.consideration_id is None):
            return _reject('advance_consideration_not_fulfilled')
        SocialEvidence.objects.create(agreement=agreement, side=side, receipt=evidence)
        setattr(agreement, column, request_id)
        agreement.save(update_fields=[column])
        kind = 'consideration_delivered' if side == 'consideration' else 'performed'
        event_id = _record(agreement, actor, kind, request_id)
        return True, 'world_work_receipt_verified', event_id, agreement

    if operation == 'social_perform':
        other = _other(agreement, actor)
        if a['activity'] != agreement.terms['activity'] or a['activity'] not in PHYSICAL:
            return _reject('activity_not_currently_agreed')
        if not _colocated(actor, other) or agreement.performance_id:
            return _reject('not_colocated_or_already_performed')
        if (agreement.terms['consideration'] != 'none'
                and agreement.terms['exchange_order'] == 'before'
                and agreement.consideration_id is None):
            return _reject('advance_consideration_not_fulfilled')
        # A world-authenticated, witnessed interaction event is created here;
        # ordinary untrusted 'pose' alone never marks physical performance.
        agreement.performance_id = request_id
        agreement.save(update_fields=['performance_id'])
        return True, 'world_witnessed_physical_interaction', _record(
            agreement, actor, 'performed', request_id,
        ), agreement
    raise AssertionError('Validated action not dispatched')


def agreement_summary(actor, agreement_id):
    """Read an agreement only if the querying character is a party."""
    agreement_id = _id(agreement_id)
    row = SocialAgreement.objects.filter(pk=agreement_id).first()
    if row is None or actor.dbref not in (row.first_dbref, row.second_dbref):
        return {'agreement_id': agreement_id, 'status': 'unknown'}
    return {
        'agreement_id': row.agreement_id,
        'status': row.state, 'revision': row.revision,
        'proposer_dbref': row.proposer_dbref,
        'recipient_dbref': row.recipient_dbref,
        'initiator_dbref': row.initiator_dbref,
        'activity': row.terms['activity'], 'consideration': row.terms['consideration'],
        'scope': row.terms['scope'], 'exchange_order': row.terms['exchange_order'],
        'accepted': row.accepted_at is not None,
        'performed': bool(row.performance_id),
        'consideration_delivered': bool(row.consideration_id),
        'breached': bool(row.breached),
    }