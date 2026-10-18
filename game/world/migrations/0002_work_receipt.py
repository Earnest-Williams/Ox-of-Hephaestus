"""Add one world-wide unique receipt namespace for requested shipboard work."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("world", "0001_crew_event")]

    operations = [
        migrations.CreateModel(
            name="WorkReceipt",
            fields=[
                ("request_id", models.CharField(max_length=32, primary_key=True,
                                                serialize=False)),
                ("actor_dbref", models.CharField(max_length=32)),
                ("target", models.CharField(max_length=32)),
                ("operation", models.CharField(max_length=48)),
                ("arguments", models.JSONField(default=dict)),
                ("outcome", models.JSONField(default=dict)),
                ("game_time", models.FloatField()),
            ],
        ),
        migrations.AddIndex(
            model_name="workreceipt",
            index=models.Index(fields=["actor_dbref", "game_time"],
                               name="ox_work_actor_time"),
        ),
    ]
