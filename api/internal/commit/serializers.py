import logging

from rest_framework import serializers
from shared.reports.types import TOTALS_MAP

from api.internal.owner.serializers import OwnerSerializer
from api.shared.commit.serializers import CommitTotalsSerializer
from core.models import Commit

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

    def get_report(self, commit: Commit):
        commit_report = commit.reports.select_related(
            "reportdetails", "reportleveltotals"
        ).first()

        return {
            "files": [
                {
                    "name": file["filename"],
                    "totals": CommitTotalsSerializer(
                        {key: val for key, val in zip(TOTALS_MAP, file["file_totals"])}
                    ).data,
                }
                for file in commit_report.reportdetails.files_array
            ],
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
