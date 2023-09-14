from rest_framework.exceptions import NotFound
from rest_framework.generics import CreateAPIView, RetrieveAPIView, UpdateAPIView
from shared.celery_config import label_analysis_task_name

from codecov_auth.authentication.repo_auth import RepositoryTokenAuthentication
from codecov_auth.permissions import SpecificScopePermission
from labelanalysis.models import LabelAnalysisRequest, LabelAnalysisRequestState
from labelanalysis.serializers import LabelAnalysisRequestSerializer
from services.task import TaskService


class LabelAnalysisRequestCreateView(CreateAPIView):
    serializer_class = LabelAnalysisRequestSerializer
    authentication_classes = [RepositoryTokenAuthentication]
    permission_classes = [SpecificScopePermission]
    # TODO Consider using a different permission scope
    required_scopes = ["static_analysis"]

    def perform_create(self, serializer):
        instance = serializer.save(state_id=LabelAnalysisRequestState.CREATED.db_id)
        TaskService().schedule_task(
            label_analysis_task_name,
            kwargs=dict(request_id=instance.id),
            apply_async_kwargs=dict(),
        )
        return instance


class LabelAnalysisRequestDetailView(RetrieveAPIView, UpdateAPIView):
    serializer_class = LabelAnalysisRequestSerializer
    authentication_classes = [RepositoryTokenAuthentication]
    permission_classes = [SpecificScopePermission]
    # TODO Consider using a different permission scope
    required_scopes = ["static_analysis"]

    def patch(self, request, *args, **kwargs):
        # This is called by the CLI to patch the request_labels information after it's collected
        # First we let rest_framework validate and update the larq object
        response = super().patch(request, *args, **kwargs)
        if response.status_code == 200:
            # IF the larq update was successful
            # we trigger the task again for the same larq to update the result saved
            # The result saved is what we use to get metrics
            uid = self.kwargs.get("external_id")
            larq = LabelAnalysisRequest.objects.get(external_id=uid)
            TaskService().schedule_task(
                label_analysis_task_name,
                kwargs=dict(request_id=larq.id),
                apply_async_kwargs=dict(),
            )
        return response

    def get_object(self):
        uid = self.kwargs.get("external_id")
        try:
            return LabelAnalysisRequest.objects.get(external_id=uid)
        except LabelAnalysisRequest.DoesNotExist:
            raise NotFound("No such Label Analysis exists")
