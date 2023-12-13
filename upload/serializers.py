from django.conf import settings
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
    ci_url = serializers.CharField(source="build_url", required=False, allow_null=True)
    version = serializers.CharField(write_only=True, required=False)
    url = serializers.SerializerMethodField()
    storage_path = serializers.CharField(write_only=True, required=False)

    class Meta:
        read_only_fields = (
            "external_id",
            "created_at",
            "raw_upload_location",
            "state",
            "provider",
            "upload_type",
            "url",
        )
        fields = read_only_fields + (
            "ci_url",
            "flags",
            "env",
            "name",
            "job_code",
            "version",
            "storage_path",
        )
        model = ReportSession

    raw_upload_location = serializers.SerializerMethodField()

    def get_raw_upload_location(self, obj: ReportSession):
        repo = obj.report.commit.repository
        archive_service = ArchiveService(repo)
        return archive_service.create_presigned_put(obj.storage_path)

    def get_url(self, obj: ReportSession):
        repository = obj.report.commit.repository
        commit = obj.report.commit
        return f"{settings.CODECOV_DASHBOARD_URL}/{repository.author.service}/{repository.author.username}/{repository.name}/commit/{commit.commitid}"

    def create(self, validated_data):
        flag_names = (
            validated_data.pop("flags") if "flags" in validated_data.keys() else []
        )
        _ = (
            validated_data.pop("version")
            if "version" in validated_data.keys()
            else None
        )
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
        report = (
            CommitReport.objects.coverage_reports()
            .filter(
                code=validated_data.get("code"),
                commit_id=validated_data.get("commit_id"),
            )
            .first()
        )
        if report:
            if report.report_type is None:
                report.report_type = CommitReport.ReportType.COVERAGE
                report.save()
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
