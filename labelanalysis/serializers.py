from rest_framework import exceptions, serializers

from core.models import Commit
from labelanalysis.models import LabelAnalysisRequest, LabelAnalysisRequestState


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
            "processing_params",
        )
        read_only_fields = ("result", "external_id")

    def get_state(self, obj):
        return LabelAnalysisRequestState.enum_from_int(obj.state_id).name.lower()
