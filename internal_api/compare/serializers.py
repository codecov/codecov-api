from rest_framework import serializers

from internal_api.commit.serializers import CommitSerializer, ReportSerializer, ReportWithoutLinesSerializer


class FlagComparisonSerializer(serializers.Serializer):
    name = serializers.CharField(source='flag_name')
    base_report_totals = serializers.JSONField(source='base_report.totals._asdict')
    head_report_totals = serializers.JSONField(source='head_report.totals._asdict')
    diff_totals = serializers.JSONField(source='diff_totals._asdict')

    
class CommitsComparisonSerializer(serializers.Serializer):
    commit_uploads = CommitSerializer(many=True, source='upload_commits')
    git_commits = serializers.JSONField()


class ComparisonDetailsSerializer(serializers.Serializer):
    base_commit = serializers.CharField(source='base_commit.commitid')
    head_commit = serializers.CharField(source='head_commit.commitid')
    base_report = ReportWithoutLinesSerializer()
    head_report = ReportWithoutLinesSerializer()
    git_commits = serializers.JSONField()


class ComparisonFullSrcSerializer(serializers.Serializer):
    base_commit = serializers.CharField(source='base_commit.commitid')
    head_commit = serializers.CharField(source='head_commit.commitid')
    base_report = ReportSerializer()
    head_report = ReportSerializer()
    src_diff = serializers.JSONField(source='git_comparison.diff')


class SingleFileSourceSerializer(serializers.Serializer):
    src = serializers.JSONField(source='sources')
