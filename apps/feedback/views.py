from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from apps.common.api_serializers import ApiErrorSerializer

from .serializers import FeedbackCreateSerializer, FeedbackResponseSerializer


@extend_schema(
    tags=["Feedback"],
    summary="Submit project feedback",
    description=(
        "Submit a 1–5 rating and optional comment. A calculation can be linked only when its private calculation token is also provided."
    ),
    request=FeedbackCreateSerializer,
    responses={201: FeedbackResponseSerializer, 400: ApiErrorSerializer},
    operation_id="feedback_create",
)
class FeedbackCreateView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = FeedbackCreateSerializer
    throttle_scope = "feedback"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(FeedbackResponseSerializer(obj).data, status=status.HTTP_201_CREATED)
