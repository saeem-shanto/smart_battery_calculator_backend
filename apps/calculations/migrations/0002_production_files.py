import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("calculations", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="calculation",
            name="source_mode",
            field=models.CharField(
                choices=[("upload", "Uploaded client workbook")],
                default="upload",
                max_length=12,
            ),
        ),
        migrations.AlterField(
            model_name="calculation",
            name="status",
            field=models.CharField(
                choices=[
                    ("processing", "Processing"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                ],
                default="processing",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="calculation",
            name="error_code",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="calculation",
            name="error_message",
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name="CalculationFile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("input_workbook", "Input workbook"), ("legacy_csv", "Legacy MATLAB CSV result"), ("xlsx_report", "Excel result report"), ("pdf_report", "PDF result report")], max_length=32)),
                ("filename", models.CharField(max_length=255)),
                ("original_filename", models.CharField(blank=True, max_length=255)),
                ("content_type", models.CharField(max_length=120)),
                ("size_bytes", models.PositiveBigIntegerField()),
                ("sha256", models.CharField(max_length=64)),
                ("data", models.BinaryField(editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("calculation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="files", to="calculations.calculation")),
            ],
            options={"ordering": ["kind", "filename"]},
        ),
        migrations.AddConstraint(
            model_name="calculationfile",
            constraint=models.UniqueConstraint(fields=("calculation", "kind"), name="one_file_per_calculation_kind"),
        ),
    ]
