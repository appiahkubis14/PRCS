# Generated migration to add TimeStampModel fields to Bops

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0003_bops'),
    ]

    operations = [
        migrations.AddField(
            model_name='bops',
            name='is_deleted',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='bops',
            name='added_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='bops_created',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AddField(
            model_name='bops',
            name='modified_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='bops_modified',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AddField(
            model_name='bops',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='bops',
            name='deleted_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='bops_deleted',
                to=settings.AUTH_USER_MODEL
            ),
        ),
    ]
