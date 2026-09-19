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
