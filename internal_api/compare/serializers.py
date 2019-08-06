from rest_framework import serializers

from internal_api.commit.serializers import CommitSerializer


class FlagComparisonSerializer(serializers.Serializer):
    name = serializers.CharField(source='flag_name')
    base_report_totals = serializers.JSONField(source='base_report.totals._asdict')
    head_report_totals = serializers.JSONField(source='head_report.totals._asdict')
    diff_totals = serializers.JSONField(source='diff_totals._asdict')


class CommitsComparisonSerializer(serializers.Serializer):
    commit_uploads = CommitSerializer(many=True)
    git_commits = serializers.JSONField()