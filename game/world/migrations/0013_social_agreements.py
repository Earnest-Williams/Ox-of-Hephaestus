"""G7b: persistent bilateral contract authority and durable public provenance."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('world', '0012_inquiry_learning')]

    operations = [
        migrations.CreateModel(
            name='SocialAgreement',
            fields=[
                ('agreement_id', models.CharField(max_length=32, primary_key=True, serialize=False)),
                ('pair_key', models.CharField(max_length=65)),
                ('first_dbref', models.CharField(max_length=32)),
                ('second_dbref', models.CharField(max_length=32)),
                ('proposer_dbref', models.CharField(max_length=32)),
                ('recipient_dbref', models.CharField(max_length=32)),
                ('initiator_dbref', models.CharField(max_length=32)),
                ('revision', models.PositiveSmallIntegerField(default=1)),
                ('terms', models.JSONField(default=dict)),
                ('state', models.CharField(max_length=16, default='pending')),
                ('opened_at', models.FloatField()),
                ('expires_at', models.FloatField()),
                ('accepted_at', models.FloatField(null=True)),
                ('consideration_id', models.CharField(max_length=32, null=True)),
                ('performance_id', models.CharField(max_length=32, null=True)),
                ('breached', models.BooleanField(default=False)),
            ],
            options={
                'indexes': [
                    models.Index(fields=['first_dbref', 'state'], name='ox_social_first_state'),
                    models.Index(fields=['second_dbref', 'state'], name='ox_social_second_state'),
                ],
                'constraints': [
                    models.UniqueConstraint(
                        fields=['pair_key'], condition=models.Q(state='pending'),
                        name='ox_social_one_pending_pair',
                    ),
                    models.CheckConstraint(
                        condition=models.Q(state__in=[
                            'pending', 'accepted', 'declined', 'deferred', 'withdrawn', 'expired'
                        ]), name='ox_social_state_valid',
                    ),
                    models.CheckConstraint(
                        condition=models.Q(revision__gte=1, revision__lte=100),
                        name='ox_social_revision_range',
                    ),
                    models.CheckConstraint(
                        condition=~models.Q(first_dbref=models.F('second_dbref')),
                        name='ox_social_distinct_people',
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name='SocialAgreementEvent',
            fields=[
                ('sequence', models.BigAutoField(primary_key=True, serialize=False)),
                ('request_id', models.CharField(max_length=32, unique=True)),
                ('actor_dbref', models.CharField(max_length=32)),
                ('kind', models.CharField(max_length=32)),
                ('revision', models.PositiveSmallIntegerField()),
                ('terms', models.JSONField(default=dict)),
                ('state', models.CharField(max_length=16)),
                ('game_time', models.FloatField()),
                ('agreement', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='events', to='world.socialagreement',
                )),
            ],
            options={
                'indexes': [models.Index(
                    fields=['agreement', 'sequence'], name='ox_social_events_order',
                )],
            },
        ),
        migrations.CreateModel(
            name='SocialEvidence',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('side', models.CharField(max_length=16)),
                ('agreement', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='evidence', to='world.socialagreement',
                )),
                ('receipt', models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='social_fulfillment', to='world.workreceipt',
                )),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(
                        fields=['agreement', 'side'], name='ox_social_one_evidence_side',
                    ),
                    models.CheckConstraint(
                        condition=models.Q(side__in=['activity', 'consideration']),
                        name='ox_social_evidence_side',
                    ),
                ],
            },
        ),
    ]