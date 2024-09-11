import dataclasses
import logging
from typing import List

from rest_framework import serializers

from api.internal.commit.serializers import CommitSerializer
from api.shared.commit.serializers import ReportTotalsSerializer
from services.comparison import (
    Comparison,
    ComparisonReport,
    FileComparison,
    ImpactedFile,
    Segment,
)

log = logging.getLogger(__name__)


class TotalsComparisonSerializer(serializers.Serializer):
    base = ReportTotalsSerializer()
    head = ReportTotalsSerializer()
    patch = ReportTotalsSerializer(source="diff")


class LineComparisonSerializer(serializers.Serializer):
    value = serializers.CharField()
    number = serializers.JSONField()
    coverage = serializers.JSONField()
    is_diff = serializers.BooleanField()
    added = serializers.BooleanField()
    removed = serializers.BooleanField()
    sessions = serializers.IntegerField(source="hit_count")


class FileComparisonSerializer(serializers.Serializer):
    name = serializers.JSONField()
    totals = TotalsComparisonSerializer()
    has_diff = serializers.BooleanField()
    stats = serializers.JSONField()
    change_summary = serializers.JSONField()
    lines = LineComparisonSerializer(many=True)


class ComparisonSerializer(serializers.Serializer):
    base_commit = serializers.CharField(source="base_commit.commitid")
    head_commit = serializers.CharField(source="head_commit.commitid")
    totals = TotalsComparisonSerializer()
    commit_uploads = CommitSerializer(many=True, source="upload_commits")
    diff = serializers.SerializerMethodField()
    files = serializers.SerializerMethodField()
    untracked = serializers.SerializerMethodField()

    def get_untracked(self, comparison) -> List[str]:
        return [
            f
            for f, _ in comparison.git_comparison["diff"]["files"].items()
            if f not in (comparison.base_report or [])
            and f not in comparison.head_report
        ]

    def get_diff(self, comparison) -> dict:
        return {"git_commits": comparison.git_commits}

    def get_files(self, comparison: Comparison) -> List[dict]:
        return [
            FileComparisonSerializer(file).data
            for file in comparison.files
            if self._should_include_file(file)
        ]

    def _should_include_file(self, file: FileComparison):
        if "has_diff" in self.context:
            return self.context["has_diff"] == file.has_diff
        else:
            return True


class FlagComparisonSerializer(serializers.Serializer):
    name = serializers.CharField(source="flag_name")
    base_report_totals = serializers.SerializerMethodField()
    head_report_totals = ReportTotalsSerializer(source="head_report.totals")
    diff_totals = ReportTotalsSerializer()

    def get_base_report_totals(self, obj):
        if obj.base_report:
            return ReportTotalsSerializer(obj.base_report.totals).data


class ImpactedFileSegmentSerializer(serializers.Serializer):
    header = serializers.SerializerMethodField()
    has_unintended_changes = serializers.BooleanField()
    lines = serializers.SerializerMethodField()

    def get_header(self, segment: Segment) -> serializers.CharField:
        (
            base_starting,
            base_extracted,
            head_starting,
            head_extracted,
        ) = segment.header
        base = f"{base_starting}"
        if base_extracted is not None:
            base = f"{base},{base_extracted}"
        head = f"{head_starting}"
        if head_extracted is not None:
            head = f"{head},{head_extracted}"
        return f"-{base} +{head}"

    def get_lines(self, segment: Segment) -> serializers.ListField:
        lines = []
        for line in segment.lines:
            value = line.value
            if value and line.is_diff:
                content = f"{value[0]} {value[1:]}"
            else:
                content = f" {value}"

            lines.append(
                {
                    "base_number": line.number["base"],
                    "head_number": line.number["head"],
                    "base_coverage": line.coverage["base"],
                    "head_coverage": line.coverage["head"],
                    "content": content,
                }
            )
        return lines


class ImpactedFileSegmentsSerializer(serializers.Serializer):
    segments = serializers.SerializerMethodField()

    def get_segments(self, file_path: str) -> ImpactedFileSegmentSerializer:
        file_comparison = self.context["comparison"].get_file_comparison(
            file_path, with_src=True, bypass_max_diff=True
        )
        return [
            ImpactedFileSegmentSerializer(segment).data
            for segment in file_comparison.segments
        ]


class ImpactedFileSerializer(serializers.Serializer):
    file_name = serializers.SerializerMethodField()
    base_name = serializers.CharField()
    head_name = serializers.CharField()
    is_new_file = serializers.SerializerMethodField()
    is_renamed_file = serializers.SerializerMethodField()
    is_deleted_file = serializers.SerializerMethodField()
    base_coverage = serializers.SerializerMethodField()
    head_coverage = serializers.SerializerMethodField()
    patch_coverage = serializers.SerializerMethodField()
    change_coverage = serializers.SerializerMethodField()
    misses_count = serializers.SerializerMethodField()

    def get_base_coverage(self, impacted_file: ImpactedFile) -> serializers.JSONField:
        if impacted_file.base_coverage:
            return dataclasses.asdict(impacted_file.base_coverage)

    def get_head_coverage(self, impacted_file: ImpactedFile) -> serializers.JSONField:
        if impacted_file.head_coverage:
            return dataclasses.asdict(impacted_file.head_coverage)

    def get_patch_coverage(self, impacted_file: ImpactedFile) -> serializers.JSONField:
        if impacted_file.patch_coverage:
            return dataclasses.asdict(impacted_file.patch_coverage)

    def get_file_name(self, impacted_file: ImpactedFile) -> serializers.CharField:
        return impacted_file.file_name

    def get_is_new_file(self, impacted_file: ImpactedFile) -> serializers.BooleanField:
        base_name = impacted_file.base_name
        head_name = impacted_file.head_name
        return base_name is None and head_name is not None

    def get_is_renamed_file(
        self, impacted_file: ImpactedFile
    ) -> serializers.BooleanField:
        base_name = impacted_file.base_name
        head_name = impacted_file.head_name
        return (
            base_name is not None and head_name is not None and base_name != head_name
        )

    def get_is_deleted_file(
        self, impacted_file: ImpactedFile
    ) -> serializers.BooleanField:
        base_name = impacted_file.base_name
        head_name = impacted_file.head_name
        return base_name is not None and head_name is None

    def get_change_coverage(
        self, impacted_file: ImpactedFile
    ) -> serializers.FloatField:
        return impacted_file.change_coverage

    def get_misses_count(self, impacted_file: ImpactedFile) -> serializers.IntegerField:
        return impacted_file.misses_count


class ImpactedFilesComparisonSerializer(ComparisonSerializer):
    files = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()

    def get_state(self, comparison: Comparison) -> str:
        return self.context["commit_comparison"].state

    def get_files(self, comparison: Comparison) -> List[dict]:
        commit_comparison = self.context["commit_comparison"]

        if not commit_comparison.is_processed:
            return []

        return [
            ImpactedFileSerializer(
                impacted_file, context={"comparison": comparison}
            ).data
            for impacted_file in ComparisonReport(commit_comparison).files
        ]
