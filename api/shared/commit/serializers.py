from rest_framework import serializers
from shared.reports.resources import Report, ReportFile
from shared.utils.merge import line_type


class CommitTotalsSerializer(serializers.Serializer):
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
    diff = serializers.SerializerMethodField()

    def get_coverage(self, totals):
        if totals.get("c") is None:
            return None
        else:
            return round(float(totals["c"]), 2)

    def get_complexity_ratio(self, totals):
        return (
            round((totals["C"] / totals["N"]) * 100, 2)
            if totals["C"] and totals["N"]
            else 0
        )

    def get_diff(self, totals):
        if "diff" in totals:
            return totals["diff"]


class ReportTotalsSerializer(serializers.Serializer):
    files = serializers.IntegerField()
    lines = serializers.IntegerField()
    hits = serializers.IntegerField()
    misses = serializers.IntegerField()
    partials = serializers.IntegerField()
    coverage = serializers.SerializerMethodField()
    branches = serializers.IntegerField()
    methods = serializers.IntegerField()
    messages = serializers.IntegerField()
    sessions = serializers.IntegerField()
    complexity = serializers.FloatField()
    complexity_total = serializers.FloatField()
    complexity_ratio = serializers.SerializerMethodField()
    diff = serializers.JSONField()

    def get_coverage(self, totals):
        if totals.coverage is not None:
            return round(float(totals.coverage), 2)
        return 0

    def get_complexity_ratio(self, totals):
        return (
            round((totals.complexity / totals.complexity_total) * 100, 2)
            if totals.complexity and totals.complexity_total
            else 0
        )


class ReportFileSerializer(serializers.Serializer):
    name = serializers.CharField()
    totals = ReportTotalsSerializer()
    line_coverage = serializers.SerializerMethodField()

    def get_line_coverage(self, report_file: ReportFile):
        return [
            (ln, line_type(report_line.coverage))
            for ln, report_line in report_file.lines
        ]


class ReportSerializer(serializers.Serializer):
    totals = ReportTotalsSerializer()
    files = serializers.SerializerMethodField()

    def get_files(self, report: Report):
        return [ReportFileSerializer(report.get(file)).data for file in report.files]
