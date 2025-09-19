import logging
import asyncio
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


class TopicViewSet(APIView):
    """Handle all topic-related operations"""

    def get(self, request):
        """List all topics with subscriber counts"""
        topics = asyncio.run(manager.list_topics())
        return Response({"topics": topics}, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new topic"""
        logger.info(f"REST API: Creating topic with data: {request.data}")
        serializer = TopicCreateSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                f"REST API: Invalid topic creation data: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        topic_name = serializer.validated_data['name']

        # Check if topic already exists
        existing_topic = asyncio.run(manager.get_topic(topic_name))
        if existing_topic:
            logger.warning(f"REST API: Topic '{topic_name}' already exists")
            return Response(
                {"error": "Topic already exists"},
                status=status.HTTP_409_CONFLICT
            )

        # Create topic
        created = asyncio.run(manager.create_topic(topic_name))
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


class HealthView(APIView):
    """Get health information"""

    def get(self, request):
        health_data = asyncio.run(manager.get_health())
        return Response(health_data, status=status.HTTP_200_OK)


class StatsView(APIView):
    """Get detailed statistics"""

    def get(self, request):
        stats_data = asyncio.run(manager.get_stats())
        return Response(stats_data, status=status.HTTP_200_OK)
