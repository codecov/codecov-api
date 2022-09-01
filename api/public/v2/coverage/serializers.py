from rest_framework import serializers


class MeasurementSerializer(serializers.Serializer):
    timestamp = serializers.DateTimeField(source="timestamp_bin")
    min = serializers.FloatField()
    max = serializers.FloatField()
    avg = serializers.FloatField()
