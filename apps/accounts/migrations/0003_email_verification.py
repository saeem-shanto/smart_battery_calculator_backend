from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_two_factor_security"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="verified_email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="email_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="twofactorchallenge",
            name="target_email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AlterField(
            model_name="twofactorchallenge",
            name="purpose",
            field=models.CharField(
                choices=[
                    ("login_user", "User login"),
                    ("login_admin", "Admin login"),
                    ("enable", "Enable two-factor authentication"),
                    ("verify_email", "Verify account email"),
                ],
                max_length=32,
            ),
        ),
    ]
