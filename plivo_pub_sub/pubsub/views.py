import logging
import asyncio
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .state import manager
from .serializers import (
    TopicCreateSerializer,
    TopicListSerializer,
    HealthSerializer,
    StatsSerializer
)

logger = logging.getLogger(__name__)


class APIKeyMixin:
    """Mixin to handle API key authentication"""

    def validate_api_key(self, request):
        """Validate API key from header or query parameter"""
        api_key = request.headers.get(
            'X-API-Key') or request.GET.get('api_key')

        # Get valid keys from settings
        valid_keys = getattr(settings, 'PUBSUB_API_KEYS', [
                             'plivo-test-key', 'demo-key', 'test-123'])

        if not api_key or api_key not in valid_keys:
            return False, Response(
                {"error": "Invalid or missing API key"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        return True, None


class TopicViewSet(APIKeyMixin, APIView):
    """Handle all topic-related operations"""

    def get(self, request):
        """List all topics with subscriber counts"""
        # Validate API key
        is_valid, error_response = self.validate_api_key(request)
        if not is_valid:
            return error_response

        # Check if shutdown is initiated
        if manager.shutdown_initiated:
            return Response(
                {"error": "Service unavailable - server shutting down"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        topics = asyncio.run(manager.list_topics())
        return Response({"topics": topics}, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new topic"""
        # Validate API key
        is_valid, error_response = self.validate_api_key(request)
        if not is_valid:
            return error_response

        # Check if shutdown is initiated
        if manager.shutdown_initiated:
            return Response(
                {"error": "Service unavailable - server shutting down"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        logger.info(f"REST API: Creating topic with data: {request.data}")
        serializer = TopicCreateSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                f"REST API: Invalid topic creation data: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        topic_name = serializer.validated_data['name']
        ring_size = request.data.get('ring_size', getattr(
            settings, 'PUBSUB_DEFAULT_RING_BUFFER_SIZE', 100))

        # Validate ring_size
        max_ring_size = getattr(settings, 'PUBSUB_MAX_RING_BUFFER_SIZE', 10000)
        if not isinstance(ring_size, int) or ring_size < 1 or ring_size > max_ring_size:
            return Response(
                {"error": f"ring_size must be an integer between 1 and {max_ring_size}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if topic already exists
        existing_topic = asyncio.run(manager.get_topic(topic_name))
        if existing_topic:
            logger.warning(f"REST API: Topic '{topic_name}' already exists")
            return Response(
                {"error": "Topic already exists"},
                status=status.HTTP_409_CONFLICT
            )

        # Create topic
        created = asyncio.run(manager.create_topic(
            topic_name, ring_size=ring_size))
        if created:
            logger.info(f"REST API: Successfully created topic '{topic_name}'")
            return Response(
                {"status": "created", "topic": topic_name},
                status=status.HTTP_201_CREATED
            )
        else:
            logger.error(f"REST API: Failed to create topic '{topic_name}'")
            return Response(
                {"error": "Failed to create topic"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, topic_name):
        """Delete a topic"""
        # Validate API key
        is_valid, error_response = self.validate_api_key(request)
        if not is_valid:
            return error_response

        # Check if shutdown is initiated
        if manager.shutdown_initiated:
            return Response(
                {"error": "Service unavailable - server shutting down"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        deleted = asyncio.run(manager.delete_topic(topic_name))
        if deleted:
            return Response(
                {"status": "deleted", "topic": topic_name},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"error": "Topic not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class HealthView(APIKeyMixin, APIView):
    """Get health information"""

    def get(self, request):
        # Validate API key
        is_valid, error_response = self.validate_api_key(request)
        if not is_valid:
            return error_response

        health_data = asyncio.run(manager.get_health())
        # Add shutdown status to health data
        health_data["shutdown_initiated"] = manager.shutdown_initiated
        return Response(health_data, status=status.HTTP_200_OK)


class StatsView(APIKeyMixin, APIView):
    """Get detailed statistics"""

    def get(self, request):
        # Validate API key
        is_valid, error_response = self.validate_api_key(request)
        if not is_valid:
            return error_response

        stats_data = asyncio.run(manager.get_stats())
        return Response(stats_data, status=status.HTTP_200_OK)


class ShutdownView(APIKeyMixin, APIView):
    """Initiate graceful shutdown"""

    def post(self, request):
        # Validate API key
        is_valid, error_response = self.validate_api_key(request)
        if not is_valid:
            return error_response

        if manager.shutdown_initiated:
            return Response(
                {"message": "Shutdown already initiated"},
                status=status.HTTP_200_OK
            )

        # Initiate shutdown in background
        import asyncio
        asyncio.create_task(manager.initiate_shutdown())

        return Response(
            {"message": "Graceful shutdown initiated"},
            status=status.HTTP_200_OK
        )
