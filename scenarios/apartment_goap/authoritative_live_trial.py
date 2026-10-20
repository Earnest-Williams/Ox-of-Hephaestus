"""G7b: GOAP-selected negotiation *executed* by authoritative Evennia commands.

Unlike the earlier illustration, a GOAP choice is not applied to a local
contract simulator before the world acknowledges a durable oxwork receipt.
The offline board is retained solely as an independently checked mirror for
comparative GOAP decisions. Server receipt + other-party addressed event are
required before a mind is told its negotiated action happened.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import secrets

from ox_ai.ports.evennia.client import EvenniaWebSocketClient
from ox_ai.scenarios.apartment_extended import ApartmentExpanded, make_pair

URL = 'ws://127.0.0.1:4002'
ROLES = ('clara', 'ben')
NAMES = ('OxSocialClara', 'OxSocialBen')
SOCIAL_MOVES = frozenset({
    'withdraw_agreement', 'deliver_consideration', 'perform_agreement',
})


def make_token(payload):
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':'),
                                               sort_keys=True).encode('utf-8')).decode('ascii').rstrip('=')


async def matching_oob(client, kind, *, predicate=lambda data: True):
    async with asyncio.timeout(16):
        packet = await client.receive_matching(
            lambda p: (p.kind == kind and bool(p.args)
                       and isinstance(p.args[0], dict)
                       and predicate(p.args[0])),
            frame_budget=100,
        )
        return packet.args[0]


async def social_command(client, other, operation, payload):
    request_id = secrets.token_hex(16)
    await client.send_line('oxwork ' + request_id + ' ' + operation
                           + ' social ' + make_token(payload))
    receipt = await matching_oob(client, 'ox_receipt', predicate=lambda v:
                                 v.get('request_id') == request_id)
    if receipt.get('status') != 'succeeded' or not receipt.get('source_event_id'):
        raise AssertionError('World refused proposed GOAP action: ' + str(receipt))
    event_kind = 'social_' + receipt['event_kind']
    seen = await matching_oob(other, 'ox_event', predicate=lambda v:
                              v.get('kind') == event_kind
                              and v.get('datum_history_id') == receipt['history_id']
                              and v.get('datum_agreement_id') == receipt.get('agreement_id')
                              and v.get('sender_dbref') == client.character_dbref)
    if seen.get('datum_revision') != receipt['revision']:
        raise AssertionError('Listener saw the wrong agreement revision')
    return receipt, seen


async def status(client, agreement_id):
    await client.send_line('oxsocialstatus ' + agreement_id)
    return await matching_oob(client, 'ox_social_status', predicate=lambda v:
                              v.get('agreement_id') == agreement_id)


async def open_clients():
    if os.environ.get('OX_SOCIAL_GOAP_LIVE_CI') != '1':
        raise PermissionError('Real social test requires disposable CI accounts')
    ids = json.loads(Path('.ox-state/g7-social-ids.json').read_text())
    if set(ids) != set(ROLES) or len(set(ids.values())) != 2:
        raise PermissionError('Expected two independent authenticated characters')
    password = os.environ['OX_PROBE_PASSWORD']
    clients = [EvenniaWebSocketClient(URL, name, password, ids[role], timeout=15)
               for role, name in zip(ROLES, NAMES)]
    try:
        await asyncio.gather(*(c.open() for c in clients))
        if not all(c.authenticated for c in clients):
            raise PermissionError('World has not authenticated both identities')
        for client in clients:
            await client.send_line('look')
            await client.expect_text("Clara's Apartment")
        return clients, ids
    except BaseException:
        await asyncio.gather(*(c.close() for c in clients), return_exceptions=True)
        raise


async def goap_trial(variant, cap=64):
    if variant not in ('mutual', 'mismatch', 'reconsider'):
        raise ValueError('Only evidence-free agreements in this live pilot')
    scene = ApartmentExpanded(*make_pair(variant))
    mapping = {}     # operator-local shadow ID -> actual durable world ID
    observations = []
    clients, ids = await open_clients()
    try:
        for turn in range(cap):
            index = turn % 2
            mind = scene.people[index]
            other = clients[1-index]
            if variant == 'reconsider' and turn == 6:
                mind.private_news(resentment_delta=100, hope_delta=-55,
                                  comfort_delta=-35)
            choice = mind.propose()
            if choice is None:
                if all('ended' in a.beliefs for a in scene.people):
                    break
                continue
            if choice.action.startswith('propose_'):
                if choice.terms.consideration != 'none':
                    raise AssertionError('Material exchanges require separately verified receipts')
                operation = 'social_propose'
                payload = {'recipient': ids[ROLES[1-index]],
                           'terms': asdict(choice.terms)}
            elif choice.action.startswith('respond_'):
                operation = 'social_reply'
                payload = {'agreement_id': mapping[choice.offer_id],
                           'revision': choice.revision, 'answer': choice.response}
                if choice.response == 'counter':
                    payload['counter'] = asdict(choice.terms)
            elif choice.action == 'withdraw_agreement':
                operation = 'social_withdraw'
                payload = {'agreement_id': mapping[choice.offer_id],
                           'revision': choice.revision}
            elif choice.action == 'perform_agreement':
                operation = 'social_perform'
                payload = {'agreement_id': mapping[choice.offer_id],
                           'revision': choice.revision,
                           'activity': choice.terms.activity}
            elif choice.action == 'deliver_consideration':
                raise AssertionError('No invented resource transfer is permitted live')
            else:
                operation = None
                await clients[index].send_line('say ' + choice.line)
                own = await clients[index].expect_text(choice.line)
                heard = await other.expect_text(choice.line)
                if 'You say,' not in own or not re.search(r'\b' + mind.name + r'\s+says,', heard):
                    raise AssertionError('Speech not confirmed by BOTH real game clients')
            if operation:
                receipt, listener_event = await social_command(
                    clients[index], other, operation, payload,
                )
            # This mirror is applied AFTER world work and recipient delivery.
            scene.step(index, confirmed_choice=choice)
            if operation:
                if operation == 'social_propose':
                    local = next(reversed(scene.board.offers))
                    mapping[local] = receipt['agreement_id']
                local_id = choice.offer_id if choice.offer_id else local
                local_offer = scene.board.offers[local_id]
                world = await status(clients[index], mapping[local_id])
                if (world.get('status') != local_offer.state
                        or world.get('revision') != local_offer.revision
                        or world.get('performed') != bool(local_offer.performed_by)
                        or world.get('consideration_delivered')
                        != bool(local_offer.consideration_delivered_by)):
                    raise AssertionError('World contract diverged from GOAP shadow: '
                                         + str((world, local_offer)))
                observations.append({
                    'actor': mind.name, 'operation': operation,
                    'agreement_id': mapping[local_id], 'world_receipt': receipt['request_id'],
                    'revision': receipt['revision'], 'state': world['status'],
                    'heard_by_counterpart': listener_event['event_id'],
                })
            if all('ended' in a.beliefs for a in scene.people):
                break
        if not all('ended' in a.beliefs for a in scene.people):
            raise AssertionError('GOAP conversation failed to conclude before turn cap')
        performed = [e for e in observations if e['operation'] == 'social_perform']
        if variant == 'mutual' and not performed:
            raise AssertionError('Mutual scenario did not complete the agreed physical act')
        if variant in ('mismatch', 'reconsider') and performed:
            raise AssertionError('Refusal/withdrawal bypassed world physical permission')
        if variant == 'reconsider' and not any(
                e['operation'] == 'social_withdraw' for e in observations):
            raise AssertionError('Changing preferences did not revoke agreement')
        return {
            'variant': variant, 'status': 'complete', 'world_actions': observations,
            'goap_actions': list(scene.trace), 'model_calls': 0,
            'authenticated_accounts': 2,
        }
    finally:
        await asyncio.gather(*(c.close() for c in clients), return_exceptions=True)


async def recovery(phase: str, file: Path):
    """Create an accepted commitment, then complete it AFTER server reboot.

    The operator file has no authority. It merely preserves the original
    agreement ID; both new client sessions must query the surviving SQL row.
    """
    clients, ids = await open_clients()
    try:
        if phase == 'prepare':
            proposed, _ = await social_command(clients[0], clients[1], 'social_propose', {
                'recipient': ids['ben'],
                'terms': {'activity': 'hug', 'scope': 'one_time',
                          'consideration': 'none', 'exchange_order': 'after'},
            })
            agreement_id = proposed['agreement_id']
            accepted, _ = await social_command(clients[1], clients[0], 'social_reply', {
                'agreement_id': agreement_id, 'revision': 1, 'answer': 'accept',
            })
            assert accepted['status'] == 'succeeded'
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(json.dumps({'agreement_id': agreement_id, 'revision': 1}),
                            encoding='utf-8')
            return {'phase': phase, 'agreement_id': agreement_id}
        raw = json.loads(file.read_text(encoding='utf-8'))
        agreement_id = raw['agreement_id']
        pre = await status(clients[0], agreement_id)
        other = await status(clients[1], agreement_id)
        if not pre['accepted'] or pre['performed'] or pre != other:
            raise AssertionError('Durable agreement not recovered by both parties')
        proof, _ = await social_command(clients[0], clients[1], 'social_perform', {
            'agreement_id': agreement_id, 'revision': 1, 'activity': 'hug',
        })
        if not (await status(clients[1], agreement_id))['performed']:
            raise AssertionError('Recovered world agreement did not authorize action')
        return {'phase': phase, 'agreement_id': agreement_id,
                'world_receipt': proof['request_id'], 'status': 'recovered'}
    finally:
        await asyncio.gather(*(c.close() for c in clients), return_exceptions=True)


def main():
    parser = argparse.ArgumentParser(description='World-authoritative social GOAP')
    parser.add_argument('--variant', choices=('mutual', 'mismatch', 'reconsider'))
    parser.add_argument('--phase', choices=('prepare', 'resume'))
    parser.add_argument('--recovery-file', type=Path,
                        default=Path('.ox-state/g7b/recovery-identity.json'))
    parser.add_argument('--out', type=Path,
                        default=Path('.ox-state/g7b/world-authoritative.json'))
    args = parser.parse_args()
    if bool(args.variant) == bool(args.phase):
        parser.error('Select either --variant or --phase')
    result = asyncio.run(recovery(args.phase, args.recovery_file)
                         if args.phase else goap_trial(args.variant))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'status': result.get('status', result.get('phase')),
                      'variant': result.get('variant'),
                      'world_actions': len(result.get('world_actions', []))}))
    print('OX_G7B_WORLD_AUTHORITY_PASS')


if __name__ == '__main__':
    main()