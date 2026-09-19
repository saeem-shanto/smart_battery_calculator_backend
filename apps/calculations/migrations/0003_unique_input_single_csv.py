import django.db.models.deletion
import uuid
from django.db import migrations, models


def migrate_existing_artifacts(apps, schema_editor):
    Calculation = apps.get_model("calculations", "Calculation")
    CalculationFile = apps.get_model("calculations", "CalculationFile")
    StoredInputFile = apps.get_model("calculations", "StoredInputFile")
    StoredCsvResult = apps.get_model("calculations", "StoredCsvResult")

    for calculation in Calculation.objects.all().iterator():
        input_artifact = CalculationFile.objects.filter(
            calculation_id=calculation.id,
            kind="input_workbook",
        ).first()
        if input_artifact is None:
            continue

        payload = calculation.input_payload or {}
        stored_input, _ = StoredInputFile.objects.get_or_create(
            sha256=input_artifact.sha256,
            defaults={
                "canonical_filename": input_artifact.original_filename or input_artifact.filename,
                "content_type": input_artifact.content_type,
                "size_bytes": input_artifact.size_bytes,
                "data": input_artifact.data,
                "detected_format": payload.get("detected_format", ""),
                "row_count": int(payload.get("row_count") or 0),
                "parsing_warnings": calculation.warnings or [],
            },
        )
        calculation.input_file_id = stored_input.id
        calculation.save(update_fields=["input_file"])

        csv_artifact = CalculationFile.objects.filter(
            calculation_id=calculation.id,
            kind="legacy_csv",
        ).first()
        if csv_artifact is not None and not StoredCsvResult.objects.filter(input_file_id=stored_input.id).exists():
            result_payload = dict(calculation.result_payload or {})
            result_payload["battery_upfront_cost_aud"] = 0.0
            result_payload["simple_payback_years"] = None
            StoredCsvResult.objects.create(
                input_file_id=stored_input.id,
                filename=csv_artifact.filename or "Results_RPAtrail400.csv",
                content_type=csv_artifact.content_type or "text/csv",
                size_bytes=csv_artifact.size_bytes,
                sha256=csv_artifact.sha256,
                data=csv_artifact.data,
                result_payload=result_payload,
                engine_version=calculation.algorithm_version or "gnu-octave-original-matlab-v1",
                algorithm_sha256=str(result_payload.get("algorithm_sha256") or ""),
                runtime_ms=calculation.runtime_ms or 0,
            )


class Migration(migrations.Migration):
    dependencies = [("calculations", "0002_production_files")]

    operations = [
        migrations.CreateModel(
            name="StoredInputFile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("sha256", models.CharField(db_index=True, max_length=64, unique=True)),
                ("canonical_filename", models.CharField(max_length=255)),
                ("content_type", models.CharField(max_length=120)),
                ("size_bytes", models.PositiveBigIntegerField()),
                ("data", models.BinaryField(editable=False)),
                ("detected_format", models.CharField(blank=True, max_length=80)),
                ("row_count", models.PositiveIntegerField(default=0)),
                ("parsing_warnings", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="StoredCsvResult",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("filename", models.CharField(default="Results_RPAtrail400.csv", max_length=255)),
                ("content_type", models.CharField(default="text/csv", max_length=120)),
                ("size_bytes", models.PositiveBigIntegerField()),
                ("sha256", models.CharField(max_length=64)),
                ("data", models.BinaryField(editable=False)),
                ("result_payload", models.JSONField(default=dict)),
                ("engine_version", models.CharField(max_length=80)),
                ("algorithm_sha256", models.CharField(blank=True, max_length=64)),
                ("runtime_ms", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "input_file",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="csv_result",
                        to="calculations.storedinputfile",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddField(
            model_name="calculation",
            name="input_file",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="calculations",
                to="calculations.storedinputfile",
            ),
        ),
        migrations.RunPython(migrate_existing_artifacts, migrations.RunPython.noop),
        migrations.DeleteModel(name="CalculationFile"),
    ]
