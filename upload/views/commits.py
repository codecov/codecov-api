import logging

from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from codecov_auth.authentication.repo_auth import (
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    TokenlessAuth,
    TokenlessAuthentication,
)
from core.models import Commit
from services.task import TaskService
from upload.serializers import OwnerSerializer, RepositorySerializer
from upload.views.base import GetterMixin
from upload.views.uploads import CanDoCoverageUploadsPermission

log = logging.getLogger(__name__)


class CommitSerializer(serializers.Serializer):
    # required read + write fields
    commitid = serializers.CharField(required=True)

    # optional read + write fields
    parent_commit_id = serializers.CharField(required=False, allow_null=True)
    branch = serializers.CharField(required=False, allow_null=True)
    pullid = serializers.IntegerField(required=False, allow_null=True)

    # read only fields
    message = serializers.CharField(read_only=True)
    timestamp = serializers.DateTimeField(read_only=True)
    ci_passed = serializers.BooleanField(read_only=True)
    state = serializers.ChoiceField(choices=Commit.CommitStates.choices, read_only=True)
    repository = RepositorySerializer(read_only=True)
    author = OwnerSerializer(read_only=True)


class CommitViews(APIView, GetterMixin):
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
        TokenlessAuthentication,
    ]

    def _possibly_fix_branch_name(self, request, data) -> None:
        """Avoids users being able to overwrite coverage info for a branch
        that exists in the upstream repo with coverage for their fork branch.
        By pre-pending the fork name to the branch
        (the CLI might have done this already)
        """
        # This only affects tokenless uploads
        if not isinstance(request.auth, TokenlessAuth):
            return
        # Notice that at this point we already validated that this fork_slug
        # is the correct repo from the head of a PR to the upstream repo
        # with the git provider
        fork_slug = request.headers.get("X-Tokenless", None)
        branch_info = data.get("branch")
        if branch_info is None:
            # There should always be a branch in the request
            raise ValidationError("missing branch")
        # The CLI might have pre-prended the branch with something already
        if ":" in branch_info:
            _, branch_info = branch_info.split(":")
        branch_to_set = f"{fork_slug}:{branch_info}"
        if data.get("branch") != branch_to_set:
            data["branch"] = branch_to_set

    def get(self, request, *args, **kwargs):
        repository = self.get_repo()
        commits = Commit.objects.filter(repository=repository).all()
        return Response(
            {
                "count": len(commits),
                "results": CommitSerializer(commits, many=True).data,
            },
            200,
        )

    def post(self, request, *args, **kwargs):
        serializer = CommitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        self._possibly_fix_branch_name(request=request, data=data)

        repository = self.get_repo()

        commit, _created = Commit.objects.get_or_create(
            repository=repository,
            commitid=data.get("commitid"),
            defaults=dict(
                parent_commit_id=data.get("parent_commit_id"),
                branch=data.get("branch"),
                pullid=data.get("pullid"),
            ),
        )

        log.info(
            "Request to create new commit",
            extra=dict(
                repo=repository.name, commit=commit.commitid, was_created=_created
            ),
        )
        TaskService().update_commit(
            commitid=commit.commitid, repoid=commit.repository.repoid
        )

        return Response(CommitSerializer(commit).data, 201)
