from rest_framework import serializers

from codecov_auth.models import Owner
from core.models import Commit
from reports.models import ReportSession
from services.archive import ArchiveService


class UploadSerializer(serializers.ModelSerializer):
    class Meta:
        fields = (
            "download_url",
            "ci_url",
            "build_url",
            "external_id",
            "created_at",
            "external_id",
            "state",
            "upload_type",
            "flags",
            "env",
            "name",
            "provider",
            "report",
        )
        read_only_fields = (
            "download_url",
            "ci_url",
            "build_url",
            "external_id",
            "created_at",
            "external_id",
            "storage_path",
            "report",
        )
        model = ReportSession


class OwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Owner
        fields = (
            "avatar_url",
            "service",
            "username",
            "name",
            "ownerid",
            "integration_id",
        )
        read_only_fields = fields


class CommitSerializer(serializers.ModelSerializer):
    author = OwnerSerializer

    class Meta:
        model = Commit
        read_only_fields = (
            "message",
            "author",
            "timestamp",
            "ci_passed",
            "state",
        )
        fields = read_only_fields + (
            "commitid",
            "parent_commit_id",
            "pullid",
            "branch",
        )
