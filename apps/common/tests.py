from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase


class AuthTests(APITestCase):
    def test_non_staff_cannot_receive_admin_token(self):
        User = get_user_model()
        User.objects.create_user(username="user", password="test-pass-123")
        response = self.client.post(
            reverse("admin-token"),
            {"username": "user", "password": "test-pass-123"},
            format="json",
        )
        self.assertIn(response.status_code, {401, 403})
