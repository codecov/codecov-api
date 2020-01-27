from rest_framework import serializers
from rest_framework.exceptions import NotFound

from django.shortcuts import get_object_or_404

from core.models import Commit, Branch, Pull


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
            return branch.get().head

        raise NotFound(f"Invalid commit or branch: {ref}")

    def validate_base(self, base):
        return self._get_commit_or_branch(base)

    def validate_head(self, head):
        return self._get_commit_or_branch(head)


class PullIDQueryParamSerializer(serializers.Serializer):
    pullid = serializers.CharField(required=True)

    def validate(self, obj):
        repo = self.context.get("repo")
        pull = get_object_or_404(Pull, pullid=obj.get("pullid"), repository=repo)

        return {"base": pull.base, "head": pull.head}
