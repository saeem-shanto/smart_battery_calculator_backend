from unittest.mock import Mock, patch

from django.core.mail import EmailMultiAlternatives, send_mail
from django.test import SimpleTestCase, override_settings


BREVO_SETTINGS = {
    "EMAIL_BACKEND": "apps.common.email_backends.BrevoApiEmailBackend",
    "DEFAULT_FROM_EMAIL": "Smart Battery Calculator <verified@example.com>",
    "BREVO_API_KEY": "test-api-key",
    "BREVO_SENDER_EMAIL": "verified@example.com",
    "BREVO_SENDER_NAME": "Smart Battery Calculator",
    "BREVO_REPLY_TO_EMAIL": "support@example.com",
    "BREVO_API_CONNECT_TIMEOUT": 5.0,
    "BREVO_API_READ_TIMEOUT": 15.0,
}


@override_settings(**BREVO_SETTINGS)
class BrevoApiEmailBackendTests(SimpleTestCase):
    @patch("apps.common.email_backends.requests.post")
    def test_send_mail_calls_brevo_api(self, post):
        response = Mock(status_code=201)
        response.raise_for_status.return_value = None
        response.json.return_value = {"messageId": "<brevo-message-id@example>"}
        post.return_value = response

        sent = send_mail(
            "Brevo API test",
            "Hello from the Smart Battery Calculator.",
            None,
            ["recipient@example.com"],
        )

        self.assertEqual(sent, 1)
        post.assert_called_once()
        call = post.call_args
        self.assertEqual(call.args[0], "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(call.kwargs["headers"]["api-key"], "test-api-key")
        self.assertEqual(call.kwargs["json"]["sender"]["email"], "verified@example.com")
        self.assertEqual(call.kwargs["json"]["to"][0]["email"], "recipient@example.com")
        self.assertEqual(call.kwargs["json"]["textContent"], "Hello from the Smart Battery Calculator.")

    @patch("apps.common.email_backends.requests.post")
    def test_html_alternative_and_reply_to_are_preserved(self, post):
        response = Mock(status_code=201)
        response.raise_for_status.return_value = None
        response.json.return_value = {"messageId": "<brevo-html@example>"}
        post.return_value = response

        message = EmailMultiAlternatives(
            subject="Security code",
            body="Plain body",
            to=["user@example.com"],
        )
        message.attach_alternative("<p>HTML body</p>", "text/html")

        self.assertEqual(message.send(), 1)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["textContent"], "Plain body")
        self.assertEqual(payload["htmlContent"], "<p>HTML body</p>")
        self.assertEqual(payload["replyTo"]["email"], "support@example.com")

    @patch("apps.common.email_backends.requests.post")
    def test_provider_error_is_raised_for_security_layer_to_convert_to_503(self, post):
        import requests

        response = Mock(status_code=401)
        response.json.return_value = {"message": "Key not found"}
        error = requests.HTTPError("401 Client Error", response=response)
        response.raise_for_status.side_effect = error
        post.return_value = response

        with self.assertRaises(requests.HTTPError):
            send_mail(
                "Failure test",
                "Provider should reject this request.",
                None,
                ["recipient@example.com"],
            )
