"""Initial indexed world-owned, addressed event journal."""
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CrewEvent",
            fields=[
                ("sequence", models.BigAutoField(
                    primary_key=True, serialize=False,
                )),
                ("event_id", models.CharField(
                    max_length=64, null=True, unique=True,
                )),
                ("recipient_dbref", models.CharField(max_length=32)),
                ("sender_dbref", models.CharField(
                    max_length=32, null=True,
                )),
                ("kind", models.CharField(max_length=64)),
                ("details", models.JSONField(default=dict)),
                ("text", models.TextField(default="")),
                ("game_time", models.FloatField()),
            ],
        ),
        migrations.AddIndex(
            model_name="crewevent",
            index=models.Index(
                fields=["recipient_dbref", "sequence"],
                name="ox_event_recipient_seq",
            ),
        ),
    ]
