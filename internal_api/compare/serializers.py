from rest_framework import serializers


class FlagComparisonSerializer(serializers.Serializer):
    base_report_totals = serializers.JSONField(source='base_report.totals._asdict')
    head_report_totals = serializers.JSONField(source='head_report.totals._asdict')
    diff_totals = serializers.JSONField(source='diff_totals._asdict')
