from rest_framework import serializers

from api.public.v2.commit.serializers import CommitSerializer
from api.shared.commit.serializers import ReportTotalsSerializer
from api.shared.compare.serializers import (
    ComparisonSerializer as BaseComparisonSerializer,
)


class ComparisonSerializer(BaseComparisonSerializer):
    commit_uploads = CommitSerializer(many=True, source="upload_commits")


class ComponentComparisonSerializer(serializers.Serializer):
    component_id = serializers.CharField(source="component.component_id")
    name = serializers.CharField(source="component.name")

    # field names here are meant to match `FlagComparisonSerializer`
    base_report_totals = ReportTotalsSerializer(source="base_totals")
    head_report_totals = ReportTotalsSerializer(source="head_totals")
    diff_totals = ReportTotalsSerializer(source="patch_totals")
