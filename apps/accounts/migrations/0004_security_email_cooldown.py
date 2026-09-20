from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_email_verification"),
    ]

    operations = [
        migrations.CreateModel(
            name="SecurityEmailCooldown",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action",
                    models.CharField(
                        choices=[("password_reset", "Password reset")],
                        max_length=32,
                    ),
                ),
                ("target_hash", models.CharField(max_length=64)),
                ("last_requested_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["updated_at"], name="accounts_sec_email_updated_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("action", "target_hash"),
                        name="accounts_sec_email_unique",
                    ),
                ],
            },
        ),
    ]
