from rest_framework import serializers

from api.shared.commit.serializers import ReportSerializer


class CoverageReportSerializer(ReportSerializer):
    commit_file_url = serializers.CharField(
        label="Codecov url to see file coverage on commit. Can be unreliable with partial path names."
    )
