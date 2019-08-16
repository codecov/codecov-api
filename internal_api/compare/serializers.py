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


class ComparisonLineCoverageSerializer(serializers.Serializer):
    base = ReportSerializer()
    head = ReportSerializer()


class ComparisonFilesSerializer(serializers.Serializer):
    base = ReportWithoutLinesSerializer()
    head = ReportWithoutLinesSerializer()


class ComparisonFullSrcSerializer(serializers.Serializer):
    base = ReportSerializer(source='base_report')
    head = ReportSerializer(source='head_report')
    src_diff = serializers.JSONField(source='git_comparison.diff')
