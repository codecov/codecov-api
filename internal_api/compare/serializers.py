from rest_framework import serializers

from internal_api.commit.serializers import (
    CommitSerializer,
    ReportSerializer,
    ReportFileSerializer,
    ReportTotalsSerializer,
)


class ComparisonSerializer(serializers.Serializer):
    base_commit = serializers.CharField(source='base_commit.commitid')
    head_commit = serializers.CharField(source='head_commit.commitid')
    base_report = ReportSerializer()
    head_report = ReportSerializer()
    commit_uploads = CommitSerializer(many=True, source='upload_commits')
    diff = serializers.SerializerMethodField()

    def _get_tracked_files(self, comparison, tracked_file_names):
        """
        Returns the diffs of changed files that are tracked by Codecov. What
        is a tracked file? It's a file for which coverage data was generated during
        the test run. An example of an untracked file would be codecov.yml.
        """
        tracked_files, files_with_source = {}, 0
        for file_name, diff_data in comparison.git_comparison["diff"]["files"].items():
            if file_name not in tracked_file_names:
                continue
            if files_with_source >= 5:
                diff_data["segments"] = None
            else:
                files_with_source += 1
            tracked_files[file_name] = diff_data
        return tracked_files

    def _get_untracked_files(self, comparison, tracked_file_names):
        return [
            file_name for file_name, _ in comparison.git_comparison["diff"]["files"].items()
            if file_name not in tracked_file_names
        ]

    def get_diff(self, comparison):
        if comparison.base_report:
            tracked_file_names = set(
                [f.name for f in comparison.base_report.file_reports()] +
                [f.name for f in comparison.head_report.file_reports()]
            )
        else:
            tracked_file_names = set(
                [f.name for f in comparison.head_report.file_reports()]
            )

        return {
            "tracked_files": self._get_tracked_files(comparison, tracked_file_names),
            "untracked_files": self._get_untracked_files(comparison, tracked_file_names),
            "git_commits": comparison.git_commits
        }


class FlagComparisonSerializer(serializers.Serializer):
    name = serializers.CharField(source='flag_name')
    base_report_totals = serializers.SerializerMethodField()
    head_report_totals = ReportTotalsSerializer(source="head_report.totals") 
    diff_totals = ReportTotalsSerializer()

    def get_base_report_totals(self, obj):
        if obj.base_report:
            return ReportTotalsSerializer(obj.base_report.totals).data


class SingleFileSourceSerializer(serializers.Serializer):
    src = serializers.JSONField()


class SingleFileDiffSerializer(serializers.Serializer):
    src_diff = serializers.JSONField()
    base_coverage = ReportFileSerializer()
    head_coverage = ReportFileSerializer()
