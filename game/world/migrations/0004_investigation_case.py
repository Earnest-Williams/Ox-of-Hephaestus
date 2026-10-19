from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("world", "0003_inventory_supply_orders")]
    operations = [
        migrations.CreateModel(
            name="InvestigationCase",
            fields=[
                ("case_id", models.CharField(max_length=32, primary_key=True, serialize=False)),
                ("status", models.CharField(max_length=16)),
                ("cause", models.CharField(max_length=32)),
                ("signals", models.JSONField(default=dict)),
                ("samples", models.JSONField(default=dict)),
                ("reports", models.JSONField(default=dict)),
                ("assessment", models.JSONField(default=dict)),
                ("created_game_time", models.FloatField()),
            ],
        ),
    ]
