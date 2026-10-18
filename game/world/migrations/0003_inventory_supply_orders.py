"""Authoritative serialised cargo units and interdepartment supply orders."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("world", "0002_work_receipt")]

    operations = [
        migrations.CreateModel(
            name="InventoryItem",
            fields=[
                ("item_id", models.CharField(max_length=48, primary_key=True,
                                            serialize=False)),
                ("kind", models.CharField(max_length=48)),
                ("state", models.CharField(max_length=16, default="stored")),
                ("location_dbref", models.CharField(max_length=32, null=True)),
                ("carrier_dbref", models.CharField(max_length=32, null=True)),
                ("reserved_order_id", models.CharField(max_length=32, null=True)),
                ("consumed_by_dbref", models.CharField(max_length=32, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="SupplyOrder",
            fields=[
                ("order_id", models.CharField(max_length=32, primary_key=True,
                                             serialize=False)),
                ("item_kind", models.CharField(max_length=48)),
                ("requester_dbref", models.CharField(max_length=32)),
                ("assigned_dbref", models.CharField(max_length=32)),
                ("delivery_room_dbref", models.CharField(max_length=32)),
                ("status", models.CharField(max_length=20)),
                ("item_id", models.CharField(max_length=48, null=True)),
                ("created_game_time", models.FloatField()),
            ],
        ),
        migrations.AddIndex(
            model_name="inventoryitem",
            index=models.Index(fields=["kind", "state", "location_dbref"],
                               name="ox_inventory_location"),
        ),
        migrations.AddIndex(
            model_name="inventoryitem",
            index=models.Index(fields=["carrier_dbref", "state"],
                               name="ox_inventory_carrier"),
        ),
        migrations.AddConstraint(
            model_name="inventoryitem",
            constraint=models.CheckConstraint(
                name="ox_inventory_one_location",
                condition=(
                    models.Q(state="stored", location_dbref__isnull=False,
                             carrier_dbref__isnull=True)
                    | models.Q(state="carried", location_dbref__isnull=True,
                               carrier_dbref__isnull=False)
                    | models.Q(state="consumed", location_dbref__isnull=True,
                               carrier_dbref__isnull=True)
                ),
            ),
        ),
        migrations.AddIndex(
            model_name="supplyorder",
            index=models.Index(fields=["assigned_dbref", "status"],
                               name="ox_supply_assignee"),
        ),
        migrations.AddIndex(
            model_name="supplyorder",
            index=models.Index(fields=["requester_dbref", "status"],
                               name="ox_supply_requester"),
        ),
    ]
