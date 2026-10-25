from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("calculations", "0006_calculation_owner")]

    operations = [
        migrations.AlterField(
            model_name="calculation",
            name="source_mode",
            field=models.CharField(
                max_length=12,
                choices=[
                    ("upload", "Uploaded client workbook"),
                    ("generated", "Generated annual PV and load profile"),
                ],
                default="upload",
            ),
        ),
    ]
