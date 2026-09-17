from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    initial=True
    dependencies=[("calculations","0001_initial")]
    operations=[
        migrations.CreateModel(
            name="Feedback",
            fields=[
                ("id",models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),
                ("rating",models.PositiveSmallIntegerField()),
                ("comment",models.TextField(blank=True,max_length=2000)),
                ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
                ("calculation",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="feedback_items",to="calculations.calculation")),
            ]
        )
    ]
