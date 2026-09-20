from rest_framework import status
from rest_framework.exceptions import APIException


class EmailServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Email security service is temporarily unavailable. Please try again later."
    default_code = "email_unavailable"


class AccountEmailNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "No active account is associated with this email address."
    default_code = "account_email_not_found"
