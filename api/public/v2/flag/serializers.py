from rest_framework import serializers


class FlagSerializer(serializers.Serializer):
    flag_name = serializers.CharField()
