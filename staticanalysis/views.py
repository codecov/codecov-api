import logging

from django.http import HttpResponse
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from shared.celery_config import static_analysis_task_name

from codecov_auth.authentication.repo_auth import RepositoryTokenAuthentication
from codecov_auth.permissions import SpecificScopePermission
from services.task import TaskService
from staticanalysis.models import StaticAnalysisSuite
from staticanalysis.serializers import StaticAnalysisSuiteSerializer

log = logging.getLogger(__name__)


class StaticAnalysisSuiteViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = StaticAnalysisSuiteSerializer
    authentication_classes = [RepositoryTokenAuthentication]
    permission_classes = [SpecificScopePermission]
    required_scopes = ["static_analysis"]
    lookup_field = "external_id"

    def get_queryset(self):
        repository = self.request.auth.get_repositories()[0]
        return StaticAnalysisSuite.objects.filter(commit__repository=repository)

    def perform_create(self, serializer):
        instance = serializer.save()
        # TODO: remove this once the CLI is calling the `finish` endpoint
        TaskService().schedule_task(
            static_analysis_task_name,
            kwargs=dict(suite_id=instance.id),
            apply_async_kwargs=dict(countdown=10),
        )
        return instance

    @action(detail=True, methods=["post"])
    def finish(self, request, *args, **kwargs):
        suite = self.get_object()
        TaskService().schedule_task(
            static_analysis_task_name,
            kwargs=dict(suite_id=suite.pk),
            apply_async_kwargs={},
        )
        return HttpResponse(status=204)
