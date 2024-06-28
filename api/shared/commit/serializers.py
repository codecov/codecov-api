from rest_framework import serializers
from shared.reports.resources import Report, ReportFile
from shared.utils.merge import line_type

from utils import round_decimals_down


class BaseTotalsSerializer(serializers.Serializer):
    files = serializers.IntegerField()
    lines = serializers.IntegerField()
    hits = serializers.IntegerField()
    misses = serializers.IntegerField()
    partials = serializers.IntegerField()
    coverage = serializers.SerializerMethodField()
    branches = serializers.IntegerField()
    methods = serializers.IntegerField()

    def get_coverage(self, totals) -> float:
        if totals.coverage is not None:
            return round_decimals_down(float(totals.coverage), 2)
        return 0


class CommitTotalsSerializer(BaseTotalsSerializer):
    files = serializers.IntegerField(source="f")
    lines = serializers.IntegerField(source="n")
    hits = serializers.IntegerField(source="h")
    misses = serializers.IntegerField(source="m")
    partials = serializers.IntegerField(source="p")
    coverage = serializers.SerializerMethodField()
    branches = serializers.IntegerField(source="b")
    methods = serializers.IntegerField(source="d")
    sessions = serializers.IntegerField(source="s")
    complexity = serializers.FloatField(source="C")
    complexity_total = serializers.FloatField(source="N")
    complexity_ratio = serializers.SerializerMethodField()
    diff = serializers.SerializerMethodField(
        label="Deprecated: this will always return 0.  Please use comparison endpoint for diff totals instead."
    )

    def get_coverage(self, totals) -> float:
        if totals.get("c") is None:
            return None
        else:
            return round_decimals_down(float(totals["c"]), 2)

    def get_complexity_ratio(self, totals) -> float:
        return (
            round_decimals_down((totals["C"] / totals["N"]) * 100, 2)
            if totals["C"] and totals["N"]
            else 0
        )

    def get_diff(self, totals) -> int:
        # deprecated
        # 0 is used as the default elsewhere in the system so we'll use that here as well (instead of null)
        return 0


class ReportTotalsSerializer(BaseTotalsSerializer):
    messages = serializers.IntegerField()
    sessions = serializers.IntegerField()
    complexity = serializers.FloatField()
    complexity_total = serializers.FloatField()
    complexity_ratio = serializers.SerializerMethodField()
    diff = serializers.JSONField()

    def get_complexity_ratio(self, totals) -> float:
        return (
            round_decimals_down((totals.complexity / totals.complexity_total) * 100, 2)
            if totals.complexity and totals.complexity_total
            else 0
        )


class UploadTotalsSerializer(BaseTotalsSerializer):
    pass


class ReportFileSerializer(serializers.Serializer):
    name = serializers.CharField(label="file path")
    totals = ReportTotalsSerializer(label="coverage totals")
    line_coverage = serializers.SerializerMethodField(
        label="line-by-line coverage values"
    )

    def get_line_coverage(self, report_file: ReportFile) -> list:
        if self.context.get("include_line_coverage"):
            return [
                (ln, line_type(report_line.coverage))
                for ln, report_line in report_file.lines
            ]

    def to_representation(self, value):
        res = super().to_representation(value)
        if not self.context.get("include_line_coverage"):
            del res["line_coverage"]
        return res


class ReportSerializer(serializers.Serializer):
    totals = ReportTotalsSerializer(label="coverage totals")
    files = serializers.SerializerMethodField(label="file specific coverage totals")

    def get_files(self, report: Report) -> ReportFileSerializer:
        return [
            ReportFileSerializer(report.get(file), context=self.context).data
            for file in report.files
        ]
