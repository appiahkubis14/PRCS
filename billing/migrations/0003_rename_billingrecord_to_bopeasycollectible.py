# Generated manually on 2026-01-17

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0002_alter_billingrecord_rev_cat_and_more"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="BillingRecord",
            new_name="BopEasyCollectible",
        ),
        migrations.AlterModelTable(
            name="bopeasycollectible",
            table="billing_bop_easy_collectible",
        ),
    ]
