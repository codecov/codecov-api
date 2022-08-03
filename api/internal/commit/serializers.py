import logging

from rest_framework import serializers
from shared.reports.types import TOTALS_MAP

from api.shared.commit.serializers import CommitTotalsSerializer
from core.models import Commit

from ..owner.serializers import OwnerSerializer

log = logging.getLogger(__name__)


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
