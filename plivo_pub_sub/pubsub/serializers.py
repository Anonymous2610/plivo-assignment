from rest_framework import serializers


class TopicCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=True)


class TopicResponseSerializer(serializers.Serializer):
    name = serializers.CharField()
    subscribers = serializers.IntegerField()


class TopicListSerializer(serializers.Serializer):
    topics = TopicResponseSerializer(many=True)


class HealthSerializer(serializers.Serializer):
    uptime_sec = serializers.IntegerField()
    topics = serializers.IntegerField()
    subscribers = serializers.IntegerField()


class StatsSerializer(serializers.Serializer):
    topics = serializers.DictField(child=serializers.DictField())
