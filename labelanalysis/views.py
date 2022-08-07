from rest_framework import exceptions, serializers
from rest_framework.generics import CreateAPIView, RetrieveAPIView

from codecov_auth.authentication.repo_auth import RepositoryTokenAuthentication
from codecov_auth.permissions import SpecificScopePermission
from core.models import Commit
from labelanalysis.models import LabelAnalysisRequest, LabelAnalysisRequestState
from services.task import TaskService


class CommitFromShaSerializerField(serializers.Field):
    def to_representation(self, commit):
        return commit.commitid

    def to_internal_value(self, commit_sha):
        commit = Commit.objects.filter(
            repository__in=self.context["request"].auth.get_repositories(),
            commitid=commit_sha,
        ).first()
        if commit is None:
            raise exceptions.NotFound()
        return commit


class LabelAnalysisRequestSerializer(serializers.ModelSerializer):
    base_commit = CommitFromShaSerializerField(required=True)
    head_commit = CommitFromShaSerializerField(required=True)
    state = serializers.SerializerMethodField()

    class Meta:
        model = LabelAnalysisRequest
        fields = (
            "base_commit",
            "head_commit",
            "requested_labels",
            "result",
            "state",
            "external_id",
        )
        read_only_fields = ("result", "external_id")

    def get_state(self, obj):
        return LabelAnalysisRequestState.enum_from_int(obj.state_id).name


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
        return LabelAnalysisRequest.objects.get(external_id=uid)
