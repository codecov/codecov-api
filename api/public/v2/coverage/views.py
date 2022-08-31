from django.db.models import Avg, Max, Min
from rest_framework import mixins, viewsets
from rest_framework.exceptions import APIException

from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions
from reports.models import RepositoryFlag
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
        queryset = MeasurementSummary.agg_by(self.get_measurement_interval()).filter(
            owner_id=self.repo.author_id,
            repo_id=self.repo.pk,
            name=self.get_measurement_name().value,
        )

        if self.get_measurement_name() == MeasurementName.FLAG_COVERAGE:
            flag = RepositoryFlag.objects.filter(
                repository_id=self.repo.pk,
                flag_name=self.kwargs["flag_name"],
            ).first()
            if not flag:
                return queryset.none()
            queryset = queryset.filter(flag_id=flag.pk)

        return (
            queryset.values("timestamp_bin", "owner_id", "repo_id", "flag_id")
            .annotate(
                value_avg=Avg("value_avg"),
                value_min=Min("value_min"),
                value_max=Max("value_max"),
            )
            .order_by("timestamp_bin")
        )

    def get_measurement_interval(self) -> Interval:
        interval_name = self.request.query_params.get("interval")
        if interval_name not in intervals:
            raise InvalidInterval()

        return intervals[interval_name]

    def get_measurement_name(self) -> MeasurementName:
        # we're reusing this viewset for multiple URLs - repo coverage and flag coverage
        if "flag_name" in self.kwargs:
            return MeasurementName.FLAG_COVERAGE
        else:
            return MeasurementName.COVERAGE
