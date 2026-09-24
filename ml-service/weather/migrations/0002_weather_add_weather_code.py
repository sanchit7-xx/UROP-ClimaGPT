"""
Stage 2 migration: add weather_code field to Weather model.

weather_code stores the WMO (World Meteorological Organization) integer code
returned by Open-Meteo. The frontend maps these to emoji + condition text.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('weather', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='weather',
            name='weather_code',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterModelOptions(
            name='weather',
            options={'ordering': ['timestamp']},
        ),
    ]
