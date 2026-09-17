from django.db import migrations, models
import uuid

class Migration(migrations.Migration):
    initial=True
    dependencies=[]
    operations=[
        migrations.CreateModel(
            name="ProfileUpload",
            fields=[
                ("id",models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),
                ("role",models.CharField(choices=[("load","Load"),("pv","PV generation"),("combined","Combined PV and load")],max_length=12)),
                ("original_name",models.CharField(max_length=255)),
                ("detected_format",models.CharField(max_length=50)),
                ("interval_minutes",models.PositiveSmallIntegerField()),
                ("value_kind",models.CharField(default="energy_kwh_interval",max_length=40)),
                ("parsed_payload",models.JSONField(default=dict)),
                ("warnings",models.JSONField(default=list)),
                ("row_count",models.PositiveIntegerField(default=0)),
                ("created_at",models.DateTimeField(auto_now_add=True)),
                ("expires_at",models.DateTimeField(db_index=True)),
            ]
        )
    ]
