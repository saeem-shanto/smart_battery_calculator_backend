from django.db import migrations, models
import apps.calculations.models


class Migration(migrations.Migration):
    dependencies = [("calculations", "0004_admin_record_controls")]

    operations = [
        migrations.AddField(
            model_name="storedinputfile",
            name="storage_file",
            field=models.FileField(
                blank=True,
                max_length=500,
                upload_to=apps.calculations.models.stored_input_upload_to,
            ),
        ),
        migrations.AlterField(
            model_name="storedinputfile",
            name="data",
            field=models.BinaryField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="storedcsvresult",
            name="storage_file",
            field=models.FileField(
                blank=True,
                max_length=500,
                upload_to=apps.calculations.models.stored_csv_upload_to,
            ),
        ),
        migrations.AlterField(
            model_name="storedcsvresult",
            name="data",
            field=models.BinaryField(blank=True, editable=False, null=True),
        ),
    ]
