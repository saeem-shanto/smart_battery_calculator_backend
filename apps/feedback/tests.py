import hashlib

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.calculations.models import Calculation


class FeedbackCalculationAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.User = get_user_model()

    def test_guest_calculation_requires_private_token(self):
        token = "guest-feedback-token"
        calculation = Calculation.objects.create(
            access_token_hash=hashlib.sha256(token.encode()).hexdigest(),
            status=Calculation.Status.COMPLETED,
        )

        denied = self.client.post(
            "/api/v1/feedback/",
            {"rating": 5, "calculation_public_id": str(calculation.public_id)},
            format="json",
        )
        self.assertEqual(denied.status_code, 400)

        allowed = self.client.post(
            "/api/v1/feedback/",
            {
                "rating": 5,
                "calculation_public_id": str(calculation.public_id),
                "calculation_access_token": token,
            },
            format="json",
        )
        self.assertEqual(allowed.status_code, 201, allowed.data)

    def test_claimed_calculation_rejects_historical_guest_token_without_owner_jwt(self):
        owner = self.User.objects.create_user(
            username="feedback-owner",
            password="Strong-Test-Pass-482!",
        )
        token = "historical-token"
        calculation = Calculation.objects.create(
            owner=owner,
            access_token_hash=hashlib.sha256(token.encode()).hexdigest(),
            status=Calculation.Status.COMPLETED,
        )

        response = self.client.post(
            "/api/v1/feedback/",
            {
                "rating": 4,
                "calculation_public_id": str(calculation.public_id),
                "calculation_access_token": token,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_claimed_calculation_owner_can_link_feedback_with_jwt(self):
        owner = self.User.objects.create_user(
            username="feedback-owner-jwt",
            password="Strong-Test-Pass-482!",
        )
        calculation = Calculation.objects.create(
            owner=owner,
            access_token_hash="f" * 64,
            status=Calculation.Status.COMPLETED,
        )
        login = self.client.post(
            "/api/v1/accounts/auth/token/",
            {"username": owner.username, "password": "Strong-Test-Pass-482!"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        response = self.client.post(
            "/api/v1/feedback/",
            {"rating": 5, "calculation_public_id": str(calculation.public_id)},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
