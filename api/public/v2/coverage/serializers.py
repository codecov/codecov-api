from rest_framework import serializers


class MeasurementSerializer(serializers.Serializer):
    timestamp = serializers.DateTimeField(source="timestamp_bin")
    min = serializers.FloatField(source="value_min")
    max = serializers.FloatField(source="value_max")
    avg = serializers.FloatField(source="value_avg")
