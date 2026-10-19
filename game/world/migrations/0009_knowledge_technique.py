"""G4e: separate learned concepts from personal equipment procedures."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("world", "0008_character_profiles_skills")]

    operations = [
        migrations.CreateModel(
            name="CharacterKnowledge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("foundation_id", models.CharField(max_length=64)),
                ("mastery", models.PositiveSmallIntegerField()),
                ("source", models.CharField(max_length=48, default="g4e_initial_estimate")),
                ("first_recorded_game_time", models.FloatField(default=0.0)),
                ("person", models.ForeignKey(
                    to="world.characterprofile", on_delete=django.db.models.deletion.PROTECT,
                    related_name="knowledge_records",
                )),
            ],
        ),
        migrations.CreateModel(
            name="CharacterTechnique",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("technique_id", models.CharField(max_length=96)),
                ("familiarity", models.PositiveSmallIntegerField()),
                ("source", models.CharField(max_length=48, default="g4e_initial_estimate")),
                ("first_recorded_game_time", models.FloatField(default=0.0)),
                ("person", models.ForeignKey(
                    to="world.characterprofile", on_delete=django.db.models.deletion.PROTECT,
                    related_name="technique_records",
                )),
            ],
        ),
        migrations.AddConstraint(
            model_name="characterknowledge",
            constraint=models.UniqueConstraint(
                fields=("person", "foundation_id"), name="ox_person_foundation_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="characterknowledge",
            constraint=models.CheckConstraint(
                condition=models.Q(mastery__lte=100), name="ox_knowledge_mastery_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="charactertechnique",
            constraint=models.UniqueConstraint(
                fields=("person", "technique_id"), name="ox_person_technique_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="charactertechnique",
            constraint=models.CheckConstraint(
                condition=models.Q(familiarity__lte=100), name="ox_technique_familiarity_range",
            ),
        ),
    ]
