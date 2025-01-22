from rest_framework import serializers


class GenAIAuthSerializer(serializers.Serializer):
    is_valid = serializers.BooleanField()
