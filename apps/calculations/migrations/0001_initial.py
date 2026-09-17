from django.db import migrations, models
import uuid

class Migration(migrations.Migration):
    initial=True
    dependencies=[]
    operations=[
        migrations.CreateModel(
            name="Calculation",
            fields=[
                ("id",models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),
                ("public_id",models.UUIDField(default=uuid.uuid4,editable=False,unique=True)),
                ("access_token_hash",models.CharField(editable=False,max_length=64)),
                ("status",models.CharField(choices=[("completed","Completed"),("failed","Failed")],default="completed",max_length=12)),
                ("source_mode",models.CharField(choices=[("simplified","Simplified inputs"),("upload","Uploaded interval data")],max_length=12)),
                ("input_payload",models.JSONField(default=dict)),
                ("result_payload",models.JSONField(default=dict)),
                ("assumptions",models.JSONField(default=list)),
                ("warnings",models.JSONField(default=list)),
                ("algorithm_version",models.CharField(blank=True,max_length=80)),
                ("runtime_ms",models.PositiveIntegerField(default=0)),
                ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
                ("updated_at",models.DateTimeField(auto_now=True)),
            ],
            options={"ordering":["-created_at"]},
        )
    ]
