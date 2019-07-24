from rest_framework import serializers

from internal_api.commit.serializers import ShortParentlessCommitSerializer


class FlagComparisonSerializer(serializers.Serializer):
    base_report_totals = serializers.JSONField(source='base_report.totals._asdict')
    head_report_totals = serializers.JSONField(source='head_report.totals._asdict')
    diff_totals = serializers.JSONField(source='diff_totals._asdict')


class CommitsComparisonSerializer(serializers.Serializer):
    commit_uploads = ShortParentlessCommitSerializer(many=True)
    git_commits = serializers.JSONField()