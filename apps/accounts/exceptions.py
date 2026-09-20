from rest_framework import status
from rest_framework.exceptions import APIException


class EmailServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Email security service is temporarily unavailable. Please try again later."
    default_code = "email_unavailable"


class ResendCooldown(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "resend_cooldown"

    def __init__(self, retry_after_seconds: int, available_at, *, code: str = "resend_cooldown"):
        self.wait = max(1, int(retry_after_seconds))
        self.retry_after_seconds = self.wait
        self.retry_at = available_at
        self.default_code = code
        super().__init__(
            detail=f"Please wait {self.wait} seconds before requesting another email.",
            code=code,
        )
