import django.db.models.deletion
from django.db import migrations, models


def populate_links_and_hashes(apps, schema_editor):
    Calculation = apps.get_model("calculations", "Calculation")
    StoredCsvResult = apps.get_model("calculations", "StoredCsvResult")

    for csv_result in StoredCsvResult.objects.select_related("input_file").all().iterator():
        if csv_result.input_file_id:
            csv_result.source_input_sha256 = csv_result.input_file.sha256
            csv_result.save(update_fields=["source_input_sha256"])

    for calculation in Calculation.objects.select_related("input_file").all().iterator():
        if not calculation.input_file_id:
            continue
        csv_result = StoredCsvResult.objects.filter(input_file_id=calculation.input_file_id).first()
        if csv_result:
            calculation.csv_result_id = csv_result.id
            calculation.save(update_fields=["csv_result"])


class Migration(migrations.Migration):
    dependencies = [("calculations", "0003_unique_input_single_csv")]

    operations = [
        migrations.AddField(
            model_name="storedcsvresult",
            name="source_input_sha256",
            field=models.CharField(blank=True, default="", max_length=64),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="calculation",
            name="csv_result",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="calculations",
                to="calculations.storedcsvresult",
            ),
        ),
        migrations.AddField(
            model_name="calculation",
            name="postcode",
            field=models.CharField(blank=True, db_index=True, max_length=12),
        ),
        migrations.AddField(
            model_name="calculation",
            name="suburb",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="calculation",
            name="state",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="calculation",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(populate_links_and_hashes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="storedcsvresult",
            name="source_input_sha256",
            field=models.CharField(db_index=True, max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name="storedcsvresult",
            name="input_file",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="csv_result",
                to="calculations.storedinputfile",
            ),
        ),
        migrations.AlterField(
            model_name="calculation",
            name="input_file",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="calculations",
                to="calculations.storedinputfile",
            ),
        ),
        migrations.AddIndex(
            model_name="calculation",
            index=models.Index(fields=["postcode", "-created_at"], name="calc_postcode_created_idx"),
        ),
        migrations.AddIndex(
            model_name="calculation",
            index=models.Index(fields=["status", "-created_at"], name="calc_status_created_idx"),
        ),
    ]
