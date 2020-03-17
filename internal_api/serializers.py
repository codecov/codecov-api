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
            head = Commit.objects.filter(repository=repo, commitid=branch.get().head)
            if head.exists():
                return head.get()
            raise NotFound(f"Invalid branch head: {branch.get().head}")
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
        try:
            return {
                "base": Commit.objects.get(commitid=pull.base, repository=repo),
                "head": Commit.objects.get(commitid=pull.head, repository=repo)
            }
        except Commit.DoesNotExist:
            raise serializers.ValidationError("Comparison requested for pull with nonexistant commit.")


class TotalsSerializer(serializers.Serializer):
    files = serializers.IntegerField(source="f")
    lines = serializers.IntegerField(source="n")
    hits = serializers.IntegerField(source="h")
    misses = serializers.IntegerField(source="m")
    partials = serializers.IntegerField(source="p")
    coverage = serializers.SerializerMethodField()
    branches = serializers.IntegerField(source="b")
    methods = serializers.IntegerField(source="d")
    sessions = serializers.IntegerField(source="s")
    diffCoverage = serializers.SerializerMethodField()

    def get_coverage(self, totals):
        return round(float(totals["c"]), 2)

    def get_diffCoverage(self, totals):
        if totals["diff"]:
            return round(float(totals["diff"][5]), 2)
        return 0
