from rest_framework import serializers

from internal_api.commit.serializers import (
    CommitSerializer,
    ReportSerializer,
    ReportWithoutLinesSerializer,
    ReportFileSerializer,
)


class FlagComparisonSerializer(serializers.Serializer):
    name = serializers.CharField(source='flag_name')
    base_report_totals = serializers.SerializerMethodField()
    head_report_totals = serializers.JSONField(source='head_report.totals._asdict')
    diff_totals = serializers.JSONField(source='diff_totals._asdict')

    def get_base_report_totals(self, obj):
        if obj.base_report:
            return obj.base_report.totals._asdict()


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
    tracked_files = serializers.SerializerMethodField()
    untracked_files = serializers.SerializerMethodField()

    def __init__(self, obj, *args, **kwargs):
        self.tracked_file_names = set(
            [f.name for f in obj.base_report.file_reports()] +
            [f.name for f in obj.head_report.file_reports()]
        )
        super().__init__(obj, *args, **kwargs)

    def get_tracked_files(self, obj):
        """
        Returns the diffs of changed files that are tracked by Codecov. What
        is a tracked file? It's a file for which coverage data was generated during
        the test run. An example of an untracked file would be codecov.yml.
        """
        tracked_files, files_with_source = {}, 0
        for file_name, diff_data in obj.git_comparison["diff"]["files"].items():
            if file_name not in self.tracked_file_names:
                continue
            if files_with_source >= 5:
                diff_data["segments"] = None
            else:
                files_with_source += 1
            tracked_files[file_name] = diff_data
        return tracked_files

    def get_untracked_files(self, obj):
        return [
            file_name for file_name, _ in obj.git_comparison["diff"]["files"].items()
            if file_name not in self.tracked_file_names
        ]


class SingleFileSourceSerializer(serializers.Serializer):
    src = serializers.JSONField(source='sources')


class SingleFileDiffSerializer(serializers.Serializer):
    src_diff = serializers.JSONField()
    base_coverage = ReportFileSerializer()
    head_coverage = ReportFileSerializer()
