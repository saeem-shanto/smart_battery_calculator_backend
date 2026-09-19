import re
import uuid

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        request.request_id = incoming if _REQUEST_ID_RE.fullmatch(incoming) else f"req_{uuid.uuid4().hex}"
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        return response


class PrivateApiNoStoreMiddleware:
    """Prevent browser/proxy caching of private or household-data API responses."""

    PRIVATE_PREFIXES = (
        "/api/v1/accounts/",
        "/api/v1/admin/",
        "/api/v1/calculations/",
        "/api/v1/profiles/",
        "/api/v1/feedback/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(self.PRIVATE_PREFIXES):
            response["Cache-Control"] = "private, no-store"
            response["Pragma"] = "no-cache"
        return response
