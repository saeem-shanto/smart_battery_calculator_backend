import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    request = context.get("request")
    request_id = getattr(request, "request_id", None)

    if response is None:
        logger.exception("Unhandled API exception request_id=%s", request_id, exc_info=exc)
        return Response(
            {
                "error": {
                    "code": "internal_error",
                    "message": "The server could not complete this request.",
                    "fields": None,
                    "request_id": request_id,
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    data = response.data
    fields = None
    message = "Request failed."
    code = "request_error"

    if isinstance(data, dict):
        if "detail" in data:
            detail = data["detail"]
            message = str(detail)
            code = getattr(detail, "code", code) or code
        else:
            fields = data
            message = "Some submitted fields are invalid."
            code = "validation_error"
    elif isinstance(data, list):
        fields = {"non_field_errors": data}
        message = "Some submitted fields are invalid."
        code = "validation_error"

    response.data = {
        "error": {
            "code": str(code),
            "message": message,
            "fields": fields,
            "request_id": request_id,
        }
    }
    return response
