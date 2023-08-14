from rest_framework import exceptions, serializers

from core.models import Commit
from labelanalysis.models import (
    LabelAnalysisProcessingError,
    LabelAnalysisRequest,
    LabelAnalysisRequestState,
)


class CommitFromShaSerializerField(serializers.Field):
    def __init__(self, *args, **kwargs):
        self.accepts_fallback = kwargs.pop("accepts_fallback", False)
        super().__init__(*args, **kwargs)

    def to_representation(self, commit):
        return commit.commitid

    def to_internal_value(self, commit_sha):
        commit = Commit.objects.filter(
            repository__in=self.context["request"].auth.get_repositories(),
            commitid=commit_sha,
        ).first()
        if commit is None:
            raise exceptions.NotFound(f"Commit {commit_sha[:7]} not found.")
        if commit.staticanalysissuite_set.exists():
            return commit
        if not self.accepts_fallback:
            raise serializers.ValidationError("No static analysis found")
        attempted_commits = []
        for _ in range(10):
            attempted_commits.append(commit.commitid)
            commit = commit.parent_commit
            if commit is None:
                raise serializers.ValidationError(
                    f"No possible commits have static analysis sent. Attempted commits: {','.join(attempted_commits)}"
                )
            if commit.staticanalysissuite_set.exists():
                return commit
        raise serializers.ValidationError(
            f"No possible commits have static analysis sent. Attempted too many commits: {','.join(attempted_commits)}"
        )


class LabelAnalysisProcessingErrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabelAnalysisProcessingError
        fields = ("error_code", "error_params")
        read_only_fields = ("error_code", "error_params")


class ProcessingErrorList(serializers.ListField):
    child = LabelAnalysisProcessingErrorSerializer()

    def to_representation(self, data):
        data = data.select_related(
            "label_analysis_request",
        ).all()
        return super().to_representation(data)


class LabelAnalysisRequestSerializer(serializers.ModelSerializer):
    base_commit = CommitFromShaSerializerField(required=True, accepts_fallback=True)
    head_commit = CommitFromShaSerializerField(required=True, accepts_fallback=False)
    state = serializers.SerializerMethodField()
    errors = ProcessingErrorList(required=False)

    def validate(self, data):
        if data["base_commit"] == data["head_commit"]:
            raise serializers.ValidationError(
                {"base_commit": "Base and head must be different commits"}
            )
        return data

    class Meta:
        model = LabelAnalysisRequest
        fields = (
            "base_commit",
            "head_commit",
            "requested_labels",
            "result",
            "state",
            "external_id",
            "errors",
        )
        read_only_fields = ("result", "external_id", "errors")

    def get_state(self, obj):
        return LabelAnalysisRequestState.enum_from_int(obj.state_id).name.lower()
