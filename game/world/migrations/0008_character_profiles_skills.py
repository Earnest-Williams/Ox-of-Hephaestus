"""G4b: authoritative persistent people and competencies, no progression yet."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("world", "0007_captain_obligation")]

    operations = [
        migrations.CreateModel(
            name="CharacterProfile",
            fields=[
                ("person_id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("character_dbref", models.CharField(max_length=32, unique=True)),
                ("schema_version", models.PositiveSmallIntegerField(default=2)),
                ("aptitudes", models.JSONField(default=dict)),
                ("psychology", models.JSONField(default=dict)),
                ("styles", models.JSONField(default=list)),
                ("source", models.CharField(max_length=48, default="ox_initial_seed")),
            ],
        ),
        migrations.CreateModel(
            name="CharacterSkill",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("skill_id", models.CharField(max_length=64)),
                ("proficiency", models.PositiveSmallIntegerField()),
                ("source", models.CharField(max_length=48, default="g3f_initial_estimate")),
                ("first_recorded_game_time", models.FloatField(default=0.0)),
                ("person", models.ForeignKey(
                    to="world.characterprofile", on_delete=django.db.models.deletion.PROTECT,
                    related_name="skill_records",
                )),
            ],
        ),
        migrations.AddConstraint(
            model_name="characterskill",
            constraint=models.UniqueConstraint(
                fields=("person", "skill_id"), name="ox_person_skill_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="characterskill",
            constraint=models.CheckConstraint(
                condition=models.Q(proficiency__lte=100), name="ox_person_skill_range",
            ),
        ),
    ]
