from rest_framework import serializers


class MeasurementSerializer(serializers.Serializer):
    timestamp = serializers.DateTimeField(
        source="timestamp_bin", label="timestamp at the start of the interval"
    )
    min = serializers.FloatField(label="minimum value in the interval")
    max = serializers.FloatField(label="maximum value in the interval")
    avg = serializers.FloatField(label="average value in the interval")