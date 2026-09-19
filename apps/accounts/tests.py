import hashlib

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.calculations.models import Calculation, StoredCsvResult, StoredInputFile


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
