"""G3e-2 additive world-only fields for challenges and follow-up experiments."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("world", "0004_investigation_case")]

    operations = [
        migrations.AddField(
            model_name="investigationcase", name="probe_key",
            field=models.CharField(max_length=32, default=""),
        ),
        migrations.AddField(
            model_name="investigationcase", name="challenges",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="investigationcase", name="probes",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="investigationcase", name="reconsiderations",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="investigationcase", name="reassessment",
            field=models.JSONField(default=dict),
        ),
    ]
