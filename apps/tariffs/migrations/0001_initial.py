from django.db import migrations, models
import uuid

class Migration(migrations.Migration):
    initial=True
    dependencies=[]
    operations=[
        migrations.CreateModel(
            name="TariffPlan",
            fields=[
                ("id",models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),
                ("name",models.CharField(max_length=120)),
                ("provider",models.CharField(blank=True,max_length=120)),
                ("kind",models.CharField(choices=[("flat","Flat"),("tou","Time of use")],default="flat",max_length=10)),
                ("flat_import_rate",models.DecimalField(blank=True,decimal_places=5,max_digits=8,null=True)),
                ("peak_import_rate",models.DecimalField(blank=True,decimal_places=5,max_digits=8,null=True)),
                ("shoulder_import_rate",models.DecimalField(blank=True,decimal_places=5,max_digits=8,null=True)),
                ("offpeak_import_rate",models.DecimalField(blank=True,decimal_places=5,max_digits=8,null=True)),
                ("feed_in_rate",models.DecimalField(decimal_places=5,default=0,max_digits=8)),
                ("daily_supply_charge",models.DecimalField(decimal_places=4,default=0,max_digits=8)),
                ("demand_charge_rate_per_kw_day",models.DecimalField(decimal_places=4,default=0,max_digits=8)),
                ("peak_start_hour",models.PositiveSmallIntegerField(default=16)),
                ("peak_end_hour",models.PositiveSmallIntegerField(default=21)),
                ("shoulder_start_hour",models.PositiveSmallIntegerField(default=7)),
                ("shoulder_end_hour",models.PositiveSmallIntegerField(default=23)),
                ("is_active",models.BooleanField(default=True)),
                ("notes",models.TextField(blank=True)),
                ("created_at",models.DateTimeField(auto_now_add=True)),
                ("updated_at",models.DateTimeField(auto_now=True)),
            ],
            options={"ordering":["provider","name"]},
        )
    ]
