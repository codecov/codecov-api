import logging

from rest_framework.generics import CreateAPIView

from codecov_auth.authentication.repo_auth import RepositoryTokenAuthentication
from codecov_auth.permissions import SpecificScopePermission
from services.task import TaskService
from staticanalysis.serializers import StaticAnalysisSuiteSerializer

log = logging.getLogger(__name__)


class StaticAnalysisSuiteView(CreateAPIView):
    serializer_class = StaticAnalysisSuiteSerializer
    authentication_classes = [RepositoryTokenAuthentication]
    permission_classes = [SpecificScopePermission]
    required_scopes = ["static_analysis"]

    def perform_create(self, serializer):
        instance = serializer.save()
        # TODO : There is no reason this trigger needs to be on a countdown here
        # Let's later add a specific endpoint to let customers trigger the check
        # whenever they tell us they are done
        TaskService().schedule_task(
            "app.tasks.staticanalysis.check_suite",
            kwargs=dict(suite_id=instance.id),
            apply_async_kwargs=dict(countdown=10),
        )
        return instance
