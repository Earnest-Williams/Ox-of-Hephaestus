"""G3e-3: independently pursued known unknowns."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("world", "0005_investigation_followup")]
    operations = [
        migrations.AddField(
            model_name="investigationcase",
            name="questions",
            field=models.JSONField(default=dict),
        ),
    ]
