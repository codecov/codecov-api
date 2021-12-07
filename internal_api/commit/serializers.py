import asyncio
import json
import logging

from rest_framework import serializers
from shared.reports.types import TOTALS_MAP

from core.models import Commit, Repository
from internal_api.owner.serializers import OwnerSerializer
from services.archive import ReportService
from services.repo_providers import RepoProviderService

log = logging.getLogger(__name__)


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


class CommitSerializer(serializers.ModelSerializer):
    author = OwnerSerializer()
    totals = CommitTotalsSerializer()

    class Meta:
        model = Commit
        fields = (
            "commitid",
            "message",
            "timestamp",
            "ci_passed",
            "author",
            "branch",
            "totals",
            "state",
        )


class CommitWithFileLevelReportSerializer(CommitSerializer):
    report = serializers.SerializerMethodField()

    def get_report(self, obj):
        # TODO: Re-evaluate this data-format when we start writing
        # the new UI components that use it.
        report_totals_by_file_name = Commit.report_totals_by_file_name(obj.id)
        return {
            "files": [
                {
                    "name": report.file_name,
                    "totals": CommitTotalsSerializer(
                        {key: val for key, val in zip(TOTALS_MAP, report.totals)}
                    ).data,
                }
                for report in report_totals_by_file_name
            ],
            "totals": CommitTotalsSerializer(obj.totals).data,
        }

    class Meta:
        model = Commit
        fields = (
            "report",
            "commitid",
            "timestamp",
            "ci_passed",
            "repository",
            "author",
            "message",
        )
