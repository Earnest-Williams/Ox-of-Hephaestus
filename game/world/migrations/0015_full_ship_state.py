from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("world", "0014_journal_continuity")]

    operations = [
        migrations.CreateModel(
            name="CanonicalShipState",
            fields=[
                ("key", models.CharField(max_length=180, primary_key=True, serialize=False)),
                ("category", models.CharField(max_length=24, db_index=True)),
                ("source_id", models.CharField(max_length=128)),
                ("source_model", models.CharField(max_length=32)),
                ("space_id", models.CharField(max_length=128, blank=True, null=True)),
                ("condition", models.CharField(max_length=48, default="serviceable")),
                ("setting", models.CharField(max_length=48, default="unverified")),
                ("quantity", models.FloatField(blank=True, null=True)),
                ("reference", models.JSONField(default=dict)),
                ("details", models.JSONField(default=dict)),
                ("revision", models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name="CanonicalShipEvent",
            fields=[
                ("sequence", models.BigAutoField(primary_key=True, serialize=False)),
                ("component_key", models.CharField(max_length=180, db_index=True)),
                ("operation", models.CharField(max_length=64)),
                ("before", models.JSONField(default=dict)),
                ("after", models.JSONField(default=dict)),
                ("actor_dbref", models.CharField(max_length=32, blank=True, null=True)),
                ("request_id", models.CharField(max_length=32, blank=True, null=True)),
                ("source_event_id", models.CharField(max_length=64, blank=True, null=True)),
                ("game_time", models.FloatField()),
            ],
        ),
        migrations.AddIndex(model_name="canonicalshipstate", index=models.Index(fields=["category", "space_id"], name="ox_full_component_loc")),
        migrations.AddIndex(model_name="canonicalshipstate", index=models.Index(fields=["category", "source_id"], name="ox_full_component_src")),
    ]
