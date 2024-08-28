from rest_framework import serializers

from api.public.v2.owner.serializers import OwnerSerializer
from api.shared.commit.serializers import CommitTotalsSerializer
from core.models import Repository


class RepoSerializer(serializers.ModelSerializer):
    name = serializers.CharField(label="repository name")
    private = serializers.BooleanField(label="indicates private vs. public repository")
    updatestamp = serializers.DateTimeField(label="last updated timestamp")
    language = serializers.CharField(label="primary programming language used")
    branch = serializers.CharField(label="default branch name")
    active = serializers.BooleanField(
        label="indicates whether the repository has received a coverage upload"
    )
    activated = serializers.BooleanField(
        label="indicates whether the repository has been manually deactivated"
    )
    author = OwnerSerializer(label="repository owner")
    totals = CommitTotalsSerializer(
        label="recent commit totals on the default branch",
        source="recent_commit_totals",
    )

    class Meta:
        model = Repository
        read_only_fields = (
            "name",
            "private",
            "updatestamp",
            "author",
            "language",
            "branch",
            "active",
            "activated",
            "totals",
        )
        fields = read_only_fields


class RepoConfigSerializer(serializers.ModelSerializer):
    upload_token = serializers.CharField(
        label="token used for uploading coverage reports for this repo"
    )

    graph_token = serializers.CharField(
        source="image_token",
        label="token used for repository graphs",
    )

    class Meta:
        model = Repository
        read_only_fields = ("upload_token", "graph_token")
        fields = read_only_fields
