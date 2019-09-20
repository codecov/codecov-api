from rest_framework import serializers

from internal_api.commit.serializers import (
    CommitSerializer,
    ReportSerializer,
    ReportWithoutLinesSerializer,
    ReportFileSerializer,
)


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
    base_report = ReportSerializer()
    head_report = ReportSerializer()
    git_commits = serializers.JSONField()


class ComparisonFullSrcSerializer(serializers.Serializer):
    src_diff = serializers.SerializerMethodField()

    def get_src_diff(self, obj):
        git_diff = obj.git_comparison["diff"]
        for i, file_diff in enumerate(git_diff["files"].items()):
            _, diff_data = file_diff
            if i >= 5:
                diff_data["segments"][0]["lines"] = []
        return git_diff


class SingleFileSourceSerializer(serializers.Serializer):
    src = serializers.JSONField(source='sources')


class SingleFileDiffSerializer(serializers.Serializer):
    src_diff = serializers.JSONField()
    base_coverage = ReportFileSerializer()
    head_coverage = ReportFileSerializer()
