from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import NotFound

from core.models import Branch, Commit, Pull
from utils.config import get_config


class CommitRefQueryParamSerializer(serializers.Serializer):
    base = serializers.CharField(required=True)
    head = serializers.CharField(required=True)

    def _get_commit_or_branch(self, ref):
        repo = self.context.get("repo")
        commit = Commit.objects.filter(repository_id=repo.repoid, commitid=ref)
        if commit.exists():
            return commit.get()

        branch = Branch.objects.filter(repository=repo, name=ref)
        if branch.exists():
            head = Commit.objects.filter(repository=repo, commitid=branch.get().head)
            if head.exists():
                return head.get()
            raise NotFound(
                f"Head commit '{branch.get().head}' for branch '{ref}' not found!"
            )
        raise NotFound(f"Commit or branch '{ref}' not found!")

    def validate_base(self, base):
        return self._get_commit_or_branch(base)

    def validate_head(self, head):
        return self._get_commit_or_branch(head)


class PullIDQueryParamSerializer(serializers.Serializer):
    pullid = serializers.CharField(required=True)

    def validate(self, obj):
        repo = self.context.get("repo")
        pull = get_object_or_404(Pull, pullid=obj.get("pullid"), repository=repo)
        return {"pull": pull}
