"""G4f: creditable practice from authenticated durable world effects."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("world", "0009_knowledge_technique")]

    operations = [
        migrations.AddField(
            model_name="characterskill", name="practice_progress",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="charactertechnique", name="practice_progress",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="CharacterLearningEvidence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_key", models.CharField(max_length=128)),
                ("task_id", models.CharField(max_length=96)),
                ("component_kind", models.CharField(max_length=16)),
                ("component_id", models.CharField(max_length=96)),
                ("credit_units", models.PositiveSmallIntegerField(default=0)),
                ("score_before", models.PositiveSmallIntegerField()),
                ("score_after", models.PositiveSmallIntegerField()),
                ("progress_before", models.PositiveSmallIntegerField(default=0)),
                ("progress_after", models.PositiveSmallIntegerField(default=0)),
                ("game_time", models.FloatField()),
                ("person", models.ForeignKey(
                    to="world.characterprofile",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="learning_evidence",
                )),
                ("receipt", models.ForeignKey(
                    to="world.workreceipt",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="learning_evidence",
                )),
            ],
        ),
        migrations.AddConstraint(
            model_name="characterlearningevidence",
            constraint=models.UniqueConstraint(
                fields=("person", "receipt", "component_kind", "component_id"),
                name="ox_learning_one_receipt_topic",
            ),
        ),
        migrations.AddConstraint(
            model_name="characterlearningevidence",
            constraint=models.UniqueConstraint(
                fields=("person", "event_key", "component_kind", "component_id"),
                name="ox_learning_one_event_topic",
            ),
        ),
        migrations.AddConstraint(
            model_name="characterlearningevidence",
            constraint=models.CheckConstraint(
                condition=models.Q(credit_units__lte=1),
                name="ox_learning_credit_bounded",
            ),
        ),
        migrations.AddConstraint(
            model_name="characterlearningevidence",
            constraint=models.CheckConstraint(
                condition=models.Q(score_before__lte=100, score_after__lte=100),
                name="ox_learning_score_bounded",
            ),
        ),
        migrations.AddConstraint(
            model_name="characterlearningevidence",
            constraint=models.CheckConstraint(
                condition=models.Q(progress_before__lte=999, progress_after__lte=999),
                name="ox_learning_progress_bound",
            ),
        ),
    ]
