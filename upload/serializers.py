from rest_framework import serializers

from codecov_auth.models import Owner
from core.models import Commit, Repository
from reports.models import CommitReport, ReportResults, ReportSession, RepositoryFlag
from services.archive import ArchiveService


class FlagListField(serializers.ListField):
    child = serializers.CharField()

    def to_representation(self, data):
        return [item.flag_name if item is not None else None for item in data.all()]


class UploadSerializer(serializers.ModelSerializer):
    flags = FlagListField(required=False)

    class Meta:
        read_only_fields = (
            "external_id",
            "created_at",
            "raw_upload_location",
            "state",
            "provider",
            "upload_type",
        )
        fields = read_only_fields + (
            "ci_url",
            "flags",
            "env",
            "name",
        )
        model = ReportSession

    raw_upload_location = serializers.SerializerMethodField()

    def get_raw_upload_location(self, obj: ReportSession):
        repo = obj.report.commit.repository
        archive_service = ArchiveService(repo)
        return archive_service.create_presigned_put(obj.storage_path)

    def create(self, validated_data):
        flag_names = validated_data.pop("flags") if validated_data.get("flags") else []
        upload = ReportSession.objects.create(**validated_data)
        flags = []
        if upload:
            repoid = upload.report.commit.repository.repoid
            for individual_flag in flag_names:
                existing_flag = RepositoryFlag.objects.filter(
                    repository_id=repoid, flag_name=individual_flag
                ).first()
                if not existing_flag:
                    existing_flag = RepositoryFlag.objects.create(
                        repository_id=repoid, flag_name=individual_flag
                    )
                flags.append(existing_flag)
            upload.flags.set(flags)
            return upload


class OwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Owner
        fields = (
            "avatar_url",
            "service",
            "username",
            "name",
            "ownerid",
        )
        read_only_fields = fields


class RepositorySerializer(serializers.ModelSerializer):
    is_private = serializers.BooleanField(source="private")

    class Meta:
        model = Repository
        fields = ("name", "is_private", "active", "language", "yaml")
        read_only_fields = fields


class CommitSerializer(serializers.ModelSerializer):
    author = OwnerSerializer(read_only=True)
    repository = RepositorySerializer(read_only=True)

    class Meta:
        model = Commit
        read_only_fields = (
            "message",
            "timestamp",
            "ci_passed",
            "state",
            "repository",
            "author",
        )
        fields = read_only_fields + (
            "commitid",
            "parent_commit_id",
            "pullid",
            "branch",
        )

    def create(self, validated_data):
        commit = Commit.objects.filter(
            repository=validated_data.get("repository"),
            commitid=validated_data.get("commitid"),
        ).first()
        if commit:
            return commit
        return super().create(validated_data)


class CommitReportSerializer(serializers.ModelSerializer):
    commit_sha = serializers.CharField(source="commit.commitid", read_only=True)

    class Meta:
        model = CommitReport
        read_only_fields = (
            "external_id",
            "created_at",
            "commit_sha",
        )
        fields = read_only_fields + ("code",)

    def create(self, validated_data):
        report = CommitReport.objects.filter(
            code=validated_data.get("code"),
            commit_id=validated_data.get("commit_id"),
        ).first()
        if report:
            return report
        return super().create(validated_data)


class ReportResultsSerializer(serializers.ModelSerializer):
    report = CommitReportSerializer(read_only=True)

    class Meta:
        model = ReportResults
        read_only_fields = (
            "external_id",
            "report",
            "state",
            "result",
            "completed_at",
        )
        fields = read_only_fields
