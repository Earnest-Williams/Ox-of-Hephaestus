"""P4f continuity: introduce one durable journal epoch and seal old events once.

The data migration reads existing world events in sequence order. Every
recipient has an independent rolling hash; historical rows are never deleted
or renumbered. This one-time scan may be proportional to the existing world
journal, but startup verification after migration is indexed.
"""
import uuid

from django.db import migrations, models


def seal_existing_history(apps, schema_editor):
    from world.journal_chain import append_digest, seed

    alias = schema_editor.connection.alias
    epochs = apps.get_model("world", "JournalEpoch")
    events = apps.get_model("world", "CrewEvent")
    generation = uuid.uuid4().hex
    epochs.objects.using(alias).create(id=1, generation=generation)
    last = {}
    batch = []
    for record in events.objects.using(alias).order_by("sequence").iterator(
        chunk_size=500
    ):
        actor = record.recipient_dbref
        event = {
            "event_id": record.event_id,
            "sequence": int(record.sequence),
            "recipient_dbref": actor,
            "sender_dbref": record.sender_dbref,
            "kind": record.kind,
            "data": dict(record.details),
            "text": record.text,
            "game_time": float(record.game_time),
        }
        digest = append_digest(last.get(actor, seed(generation, actor)), event)
        record.chain_hash = digest
        batch.append(record)
        last[actor] = digest
        if len(batch) >= 500:
            events.objects.using(alias).bulk_update(batch, ["chain_hash"])
            batch.clear()
    if batch:
        events.objects.using(alias).bulk_update(batch, ["chain_hash"])


class Migration(migrations.Migration):
    dependencies = [("world", "0013_social_agreements")]

    operations = [
        migrations.AddField(
            model_name="crewevent",
            name="chain_hash",
            field=models.CharField(max_length=64, null=True),
        ),
        migrations.CreateModel(
            name="JournalEpoch",
            fields=[
                ("id", models.PositiveSmallIntegerField(
                    default=1, primary_key=True, serialize=False,
                )),
                ("generation", models.CharField(max_length=32)),
            ],
        ),
        migrations.RunPython(seal_existing_history, migrations.RunPython.noop),
    ]
