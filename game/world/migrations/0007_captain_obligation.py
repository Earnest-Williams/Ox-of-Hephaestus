"""G3f: durable captain-owned obligations, distinct from a diagnosis."""
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("world", "0006_independent_questions")]
    operations = [
        migrations.CreateModel(
            name="CaptainObligation",
            fields=[
                ("ticket_id", models.CharField(max_length=32, primary_key=True, serialize=False)),
                ("kind", models.CharField(max_length=32)),
                ("source_ref", models.CharField(max_length=64)),
                ("priority", models.PositiveSmallIntegerField()),
                ("status", models.CharField(max_length=16, default="open")),
                ("captain_dbref", models.CharField(max_length=32)),
                ("assignment", models.JSONField(default=dict)),
                ("history", models.JSONField(default=list)),
                ("due_game_time", models.FloatField()),
                ("last_reminded_game_time", models.FloatField(default=0)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["status", "due_game_time"], name="ox_captain_due"),
                ],
            },
        ),
    ]
