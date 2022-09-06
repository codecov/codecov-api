from datetime import datetime

from rest_framework import mixins, viewsets
from rest_framework.exceptions import APIException

from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions
from reports.models import RepositoryFlag
from timeseries.helpers import (
    aggregate_measurements,
    repository_coverage_measurements_with_fallback,
)
from timeseries.models import Interval, MeasurementName, MeasurementSummary

from .filters import MeasurementFilters
from .serializers import MeasurementSerializer


class InvalidInterval(APIException):
    status_code = 422
    default_detail = "You must specify an interval (1d/7d/30d)"
    default_code = "invalid_interval"


intervals = {
    "1d": Interval.INTERVAL_1_DAY,
    "7d": Interval.INTERVAL_7_DAY,
    "30d": Interval.INTERVAL_30_DAY,
}


class CoverageViewSet(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    RepoPropertyMixin,
):
    permission_classes = [RepositoryArtifactPermissions]
    filterset_class = MeasurementFilters
    serializer_class = MeasurementSerializer

    def get_queryset(self):
        return repository_coverage_measurements_with_fallback(
            self.repo,
            self.get_measurement_interval(),
            start_date=self.request.query_params.get(
                "start_date", datetime(2000, 1, 1)
            ),
            end_date=self.request.query_params.get("end_date", datetime.now()),
            branch=self.request.query_params.get("branch"),
        )

    def get_measurement_interval(self) -> Interval:
        interval_name = self.request.query_params.get("interval")
        if interval_name not in intervals:
            raise InvalidInterval()

        return intervals[interval_name]


class FlagCoverageViewSet(CoverageViewSet):
    def get_queryset(self):
        queryset = MeasurementSummary.agg_by(self.get_measurement_interval())

        flag = RepositoryFlag.objects.filter(
            repository_id=self.repo.pk,
            flag_name=self.kwargs["flag_name"],
        ).first()
        if not flag:
            return queryset.none()

        queryset = queryset.filter(
            name=MeasurementName.FLAG_COVERAGE.value,
            owner_id=self.repo.author_id,
            repo_id=self.repo.pk,
            flag_id=flag.pk,
        )

        return aggregate_measurements(
            queryset, ["timestamp_bin", "owner_id", "repo_id", "flag_id"]
        )
