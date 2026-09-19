import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="two_factor_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="TwoFactorChallenge",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("purpose", models.CharField(choices=[("login_user", "User login"), ("login_admin", "Admin login"), ("enable", "Enable two-factor authentication")], max_length=32)),
                ("code_digest", models.CharField(blank=True, max_length=64)),
                ("expires_at", models.DateTimeField()),
                ("last_sent_at", models.DateTimeField()),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="two_factor_challenges", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user", "purpose", "consumed_at"], name="accounts_tw_user_id_322cc0_idx"),
                    models.Index(fields=["expires_at"], name="accounts_tw_expires_e094f8_idx"),
                ],
            },
        ),
    ]
