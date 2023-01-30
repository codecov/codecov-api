from cProfile import label

from rest_framework import serializers

from api.public.v2.owner.serializers import OwnerSerializer
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
        )
        fields = read_only_fields


class RepoConfigSerializer(serializers.ModelSerializer):
    upload_token = serializers.CharField(
        label="token used for uploading coverage reports"
    )

    class Meta:
        model = Repository
        read_only_fields = ("upload_token",)
        fields = read_only_fields
