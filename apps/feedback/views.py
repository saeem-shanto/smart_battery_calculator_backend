from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from .serializers import FeedbackCreateSerializer, FeedbackResponseSerializer


@extend_schema(
    tags=["Feedback"],
    request=FeedbackCreateSerializer,
    responses={201: FeedbackResponseSerializer},
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
