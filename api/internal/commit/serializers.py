from loguru import logger

from rest_framework import serializers
from shared.reports.types import TOTALS_MAP

import services.report as report_service
from api.internal.owner.serializers import OwnerSerializer
from api.shared.commit.serializers import CommitTotalsSerializer
from core.models import Commit


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

    def get_report(self, commit: Commit):
        report = report_service.build_report_from_commit(commit)
        if report is None:
            return None

        files = []
        for filename in report.files:
            file_report = report.get(filename)
            file_totals = CommitTotalsSerializer(
                {key: val for key, val in zip(TOTALS_MAP, file_report.totals)}
            )
            files.append(
                {
                    "name": filename,
                    "totals": file_totals.data,
                }
            )

        return {
            "files": files,
            "totals": CommitTotalsSerializer(commit.totals).data,
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
