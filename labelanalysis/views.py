from rest_framework.exceptions import NotFound
from rest_framework.generics import CreateAPIView, RetrieveAPIView

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
            "app.tasks.label_analysis.process",
            kwargs=dict(request_id=instance.id),
            apply_async_kwargs=dict(),
        )
        return instance


class LabelAnalysisRequestDetailView(RetrieveAPIView):
    serializer_class = LabelAnalysisRequestSerializer
    authentication_classes = [RepositoryTokenAuthentication]
    permission_classes = [SpecificScopePermission]
    # TODO Consider using a different permission scope
    required_scopes = ["static_analysis"]

    def get_object(self):
        uid = self.kwargs.get("external_id")
        try:
            return LabelAnalysisRequest.objects.get(external_id=uid)
        except LabelAnalysisRequest.DoesNotExist:
            raise NotFound("No such Label Analysis exists")
