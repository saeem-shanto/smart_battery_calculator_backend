import hashlib

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from apps.calculations.models import Calculation, StoredCsvResult, StoredInputFile
from apps.accounts.security import email_security_available


class EmailBackendConfigurationTests(SimpleTestCase):
    @override_settings(
        ACCOUNT_EMAIL_ENABLED=True,
        EMAIL_BACKEND="apps.common.email_backends.BrevoApiEmailBackend",
        BREVO_API_KEY="test-api-key",
        BREVO_SENDER_EMAIL="verified@example.com",
    )
    def test_brevo_api_backend_is_available_with_api_key_and_sender(self):
        self.assertTrue(email_security_available())

    @override_settings(
        ACCOUNT_EMAIL_ENABLED=True,
        EMAIL_BACKEND="apps.common.email_backends.BrevoApiEmailBackend",
        BREVO_API_KEY="",
        BREVO_SENDER_EMAIL="verified@example.com",
    )
    def test_brevo_api_backend_is_unavailable_without_api_key(self):
        self.assertFalse(email_security_available())

    @override_settings(
        ACCOUNT_EMAIL_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
    )
    def test_console_backend_is_available_without_external_credentials(self):
        self.assertTrue(email_security_available())

    @override_settings(
        ACCOUNT_EMAIL_ENABLED=False,
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
    )
    def test_email_security_feature_flag_disables_delivery(self):
        self.assertFalse(email_security_available())


class AccountApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_registration_returns_tokens_and_profile(self):
        response = self.client.post(
            "/api/v1/accounts/register/",
            {
                "username": "saeem_test",
                "email": "saeem@example.com",
                "first_name": "Saeem",
                "last_name": "Test",
                "password": "Strong-Test-Pass-482!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["access"])
        self.assertTrue(response.data["refresh"])
        self.assertEqual(response.data["user"]["username"], "saeem_test")
        self.assertFalse(response.data["user"]["email_verified"])
        self.assertIsNone(response.data["user"]["email_verified_at"])
        user = get_user_model().objects.get(username="saeem_test")
        self.assertTrue(hasattr(user, "battery_profile"))

    def test_authenticated_owner_can_open_retained_calculation_without_private_token(self):
        User = get_user_model()
        user = User.objects.create_user(username="owner", password="Strong-Test-Pass-482!")
        token_response = self.client.post(
            "/api/v1/accounts/auth/token/",
            {"username": "owner", "password": "Strong-Test-Pass-482!"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")
        calculation = Calculation.objects.create(
            owner=user,
            access_token_hash=hashlib.sha256(b"private-token").hexdigest(),
            status=Calculation.Status.COMPLETED,
            result_payload={},
        )
        response = self.client.get(f"/api/v1/calculations/{calculation.public_id}/")
        self.assertEqual(response.status_code, 200, response.data)

    def test_other_user_cannot_open_owned_calculation_without_private_token(self):
        User = get_user_model()
        owner = User.objects.create_user(username="owner2", password="Strong-Test-Pass-482!")
        other = User.objects.create_user(username="other", password="Strong-Test-Pass-482!")
        calculation = Calculation.objects.create(
            owner=owner,
            access_token_hash=hashlib.sha256(b"private-token").hexdigest(),
            status=Calculation.Status.COMPLETED,
            result_payload={},
        )
        token_response = self.client.post(
            "/api/v1/accounts/auth/token/",
            {"username": "other", "password": "Strong-Test-Pass-482!"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")
        response = self.client.get(f"/api/v1/calculations/{calculation.public_id}/")
        self.assertEqual(response.status_code, 403)

    def test_authenticated_user_can_claim_guest_calculation_with_private_token(self):
        User = get_user_model()
        user = User.objects.create_user(username="claimer", password="Strong-Test-Pass-482!")
        private_token = "claim-token"
        calculation = Calculation.objects.create(
            access_token_hash=hashlib.sha256(private_token.encode()).hexdigest(),
            status=Calculation.Status.COMPLETED,
            result_payload={},
        )
        token_response = self.client.post(
            "/api/v1/accounts/auth/token/",
            {"username": "claimer", "password": "Strong-Test-Pass-482!"},
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}",
            HTTP_X_CALCULATION_TOKEN=private_token,
        )
        response = self.client.post(f"/api/v1/calculations/{calculation.public_id}/claim/")
        self.assertEqual(response.status_code, 200, response.data)
        calculation.refresh_from_db()
        self.assertEqual(calculation.owner_id, user.id)

        # Ownership supersedes the historical guest token. A caller without the
        # owner JWT cannot keep using a copied pre-claim token.
        self.client.credentials(HTTP_X_CALCULATION_TOKEN=private_token)
        guest_response = self.client.get(f"/api/v1/calculations/{calculation.public_id}/")
        self.assertEqual(guest_response.status_code, 403)


class CalculationDeletionPrivacyTests(TestCase):
    def test_last_calculation_delete_removes_orphaned_binary_artifacts(self):
        input_file = StoredInputFile.objects.create(
            sha256="a" * 64,
            canonical_filename="private.csv",
            content_type="text/csv",
            size_bytes=4,
            data=b"data",
            detected_format="client_two_column_csv",
            row_count=2,
        )
        csv = StoredCsvResult.objects.create(
            input_file=input_file,
            source_input_sha256=input_file.sha256,
            filename="Results_RPAtrail400.csv",
            content_type="text/csv",
            size_bytes=4,
            sha256="b" * 64,
            data=b"1,2\n",
            result_payload={},
            engine_version="test",
        )
        calculation = Calculation.objects.create(
            access_token_hash="c" * 64,
            input_file=input_file,
            csv_result=csv,
            status=Calculation.Status.COMPLETED,
        )

        with self.captureOnCommitCallbacks(execute=True):
            calculation.delete()

        self.assertFalse(StoredCsvResult.objects.filter(pk=csv.pk).exists())
        self.assertFalse(StoredInputFile.objects.filter(pk=input_file.pk).exists())

    def test_shared_artifacts_survive_until_last_calculation_is_deleted(self):
        input_file = StoredInputFile.objects.create(
            sha256="d" * 64,
            canonical_filename="shared.csv",
            content_type="text/csv",
            size_bytes=4,
            data=b"data",
            detected_format="client_two_column_csv",
            row_count=2,
        )
        csv = StoredCsvResult.objects.create(
            input_file=input_file,
            source_input_sha256=input_file.sha256,
            filename="Results_RPAtrail400.csv",
            content_type="text/csv",
            size_bytes=4,
            sha256="e" * 64,
            data=b"1,2\n",
            result_payload={},
            engine_version="test",
        )
        first = Calculation.objects.create(access_token_hash="1" * 64, input_file=input_file, csv_result=csv)
        second = Calculation.objects.create(access_token_hash="2" * 64, input_file=input_file, csv_result=csv)

        with self.captureOnCommitCallbacks(execute=True):
            first.delete()
        self.assertTrue(StoredCsvResult.objects.filter(pk=csv.pk).exists())
        self.assertTrue(StoredInputFile.objects.filter(pk=input_file.pk).exists())

        with self.captureOnCommitCallbacks(execute=True):
            second.delete()
        self.assertFalse(StoredCsvResult.objects.filter(pk=csv.pk).exists())
        self.assertFalse(StoredInputFile.objects.filter(pk=input_file.pk).exists())


class EmailSecurityApiTests(TestCase):
    def setUp(self):
        from django.core import mail
        self.client = APIClient()
        self.mail = mail
        self.mail.outbox = []
        self.User = get_user_model()
        self.password = "Strong-Test-Pass-482!"

    def _create_2fa_user(self, username="twofactor", is_staff=False):
        from apps.accounts.models import UserProfile
        user = self.User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password=self.password,
            is_staff=is_staff,
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.two_factor_enabled = True
        profile.save(update_fields=["two_factor_enabled"])
        return user

    def test_two_factor_login_requires_otp_before_jwt(self):
        import re

        self._create_2fa_user()
        response = self.client.post(
            "/api/v1/accounts/auth/token/",
            {"username": "twofactor", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["two_factor_required"])
        self.assertNotIn("access", response.data)
        self.assertEqual(len(self.mail.outbox), 1)
        code = re.search(r"\b(\d{6})\b", self.mail.outbox[0].body).group(1)

        verify = self.client.post(
            "/api/v1/accounts/auth/2fa/verify/",
            {"challenge_id": response.data["challenge_id"], "code": code},
            format="json",
        )
        self.assertEqual(verify.status_code, 200, verify.data)
        self.assertTrue(verify.data["access"])
        self.assertTrue(verify.data["refresh"])

    @override_settings(
        EMAIL_BACKEND="apps.common.email_backends.BrevoApiEmailBackend",
        BREVO_API_KEY="",
        BREVO_SENDER_EMAIL="verified@example.com",
    )
    def test_two_factor_login_reports_email_provider_unavailable_as_503(self):
        self._create_2fa_user(username="brevodown")
        response = self.client.post(
            "/api/v1/accounts/auth/token/",
            {"username": "brevodown", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, 503, response.data)
        self.assertEqual(response.data["error"]["code"], "email_unavailable")

    def test_admin_two_factor_login_requires_otp(self):
        import re

        self._create_2fa_user(username="staff2fa", is_staff=True)
        response = self.client.post(
            "/api/v1/admin/auth/token/",
            {"username": "staff2fa", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["two_factor_required"])
        code = re.search(r"\b(\d{6})\b", self.mail.outbox[-1].body).group(1)
        verify = self.client.post(
            "/api/v1/accounts/auth/2fa/verify/",
            {"challenge_id": response.data["challenge_id"], "code": code},
            format="json",
        )
        self.assertEqual(verify.status_code, 200, verify.data)
        self.assertTrue(verify.data["user"]["is_staff"])

    def test_user_can_enable_and_disable_two_factor(self):
        import re

        user = self.User.objects.create_user(username="toggle2fa", email="toggle@example.com", password=self.password)
        token = self.client.post(
            "/api/v1/accounts/auth/token/",
            {"username": user.username, "password": self.password},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
        start = self.client.post(
            "/api/v1/accounts/me/two-factor/enable/",
            {"current_password": self.password},
            format="json",
        )
        self.assertEqual(start.status_code, 200, start.data)
        code = re.search(r"\b(\d{6})\b", self.mail.outbox[-1].body).group(1)
        verify = self.client.post(
            "/api/v1/accounts/me/two-factor/enable/verify/",
            {"challenge_id": start.data["challenge_id"], "code": code},
            format="json",
        )
        self.assertEqual(verify.status_code, 200, verify.data)
        self.assertTrue(verify.data["two_factor_enabled"])
        self.assertTrue(verify.data["email_verified"])

        disable = self.client.post(
            "/api/v1/accounts/me/two-factor/disable/",
            {"current_password": self.password},
            format="json",
        )
        self.assertEqual(disable.status_code, 200, disable.data)
        self.assertFalse(disable.data["two_factor_enabled"])

    def test_password_reset_email_changes_password(self):
        from urllib.parse import parse_qs, urlparse
        import re

        user = self.User.objects.create_user(username="resetme", email="reset@example.com", password=self.password)
        request = self.client.post(
            "/api/v1/accounts/auth/password-reset/",
            {"email": user.email},
            format="json",
        )
        self.assertEqual(request.status_code, 200, request.data)
        self.assertEqual(len(self.mail.outbox), 1)
        match = re.search(r"https?://\S+", self.mail.outbox[0].body)
        self.assertIsNotNone(match)
        query = parse_qs(urlparse(match.group(0)).query)
        new_password = "Another-Strong-Pass-732!"
        confirm = self.client.post(
            "/api/v1/accounts/auth/password-reset/confirm/",
            {
                "uid": query["uid"][0],
                "token": query["token"][0],
                "new_password": new_password,
                "confirm_password": new_password,
            },
            format="json",
        )
        self.assertEqual(confirm.status_code, 204, getattr(confirm, "data", None))
        user.refresh_from_db()
        self.assertTrue(user.check_password(new_password))

    def test_password_reset_request_rejects_email_without_active_account(self):
        response = self.client.post(
            "/api/v1/accounts/auth/password-reset/",
            {"email": "missing@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 404, response.data)
        self.assertEqual(response.data["error"]["code"], "account_email_not_found")
        self.assertEqual(len(self.mail.outbox), 0)

    def test_password_reset_does_not_require_verified_email(self):
        user = self.User.objects.create_user(
            username="unverified-reset",
            email="unverified-reset@example.com",
            password=self.password,
        )
        response = self.client.post(
            "/api/v1/accounts/auth/password-reset/",
            {"email": user.email},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["detail"], "Password reset email sent.")
        self.assertEqual(len(self.mail.outbox), 1)

    def test_user_can_verify_email_later_and_profile_exposes_status(self):
        import re

        user = self.User.objects.create_user(
            username="verifylater",
            email="verifylater@example.com",
            password=self.password,
        )
        token = self.client.post(
            "/api/v1/accounts/auth/token/",
            {"username": user.username, "password": self.password},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")

        status_before = self.client.get("/api/v1/accounts/me/email-verification/")
        self.assertEqual(status_before.status_code, 200, status_before.data)
        self.assertFalse(status_before.data["verified"])

        request_code = self.client.post("/api/v1/accounts/me/email-verification/request/", {}, format="json")
        self.assertEqual(request_code.status_code, 200, request_code.data)
        self.assertEqual(len(self.mail.outbox), 1)
        code = re.search(r"\b(\d{6})\b", self.mail.outbox[-1].body).group(1)

        verify = self.client.post(
            "/api/v1/accounts/me/email-verification/verify/",
            {"challenge_id": request_code.data["challenge_id"], "code": code},
            format="json",
        )
        self.assertEqual(verify.status_code, 200, verify.data)
        self.assertTrue(verify.data["email_verified"])
        self.assertIsNotNone(verify.data["email_verified_at"])

        status_after = self.client.get("/api/v1/accounts/me/email-verification/")
        self.assertTrue(status_after.data["verified"])
        self.assertIsNotNone(status_after.data["verified_at"])

    def test_changing_email_clears_verification_and_invalidates_old_challenge(self):
        import re

        user = self.User.objects.create_user(
            username="emailchange",
            email="first@example.com",
            password=self.password,
        )
        token = self.client.post(
            "/api/v1/accounts/auth/token/",
            {"username": user.username, "password": self.password},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
        first = self.client.post("/api/v1/accounts/me/email-verification/request/", {}, format="json")
        code = re.search(r"\b(\d{6})\b", self.mail.outbox[-1].body).group(1)

        changed = self.client.patch(
            "/api/v1/accounts/me/",
            {"email": "second@example.com"},
            format="json",
        )
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertFalse(changed.data["email_verified"])

        stale = self.client.post(
            "/api/v1/accounts/me/email-verification/verify/",
            {"challenge_id": first.data["challenge_id"], "code": code},
            format="json",
        )
        self.assertEqual(stale.status_code, 400, stale.data)
