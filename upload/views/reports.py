import logging

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from codecov_auth.authentication.repo_auth import (
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    TokenlessAuthentication,
)
from reports.models import CommitReport, ReportResults
from services.task import TaskService
from upload.views.base import GetterMixin
from upload.views.uploads import CanDoCoverageUploadsPermission

log = logging.getLogger(__name__)


class CommitReportSerializer(serializers.Serializer):
    code = serializers.CharField(allow_null=True, max_length=100)

    external_id = serializers.UUIDField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    commit_sha = serializers.CharField(source="commit.commitid", read_only=True)


class ReportViews(APIView, GetterMixin):
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
        TokenlessAuthentication,
    ]

    def get(self, request, *args, **kwargs):
        return Response(data=None, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def post(self, request, *args, **kwargs):
        serializer = CommitReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        repository = self.get_repo()
        commit = self.get_commit(repository)
        log.info(
            "Request to create new report",
            extra=dict(repo=repository.name, commit=commit.commitid),
        )
        code = data["code"]
        if code == "default":
            code = None
        report, _created = CommitReport.objects.coverage_reports().get_or_create(
            commit_id=commit.id,
            code=code,
            defaults={"report_type": CommitReport.ReportType.COVERAGE},
        )
        if report.report_type is None:
            report.report_type = CommitReport.ReportType.COVERAGE
            report.save()

        TaskService().preprocess_upload(repository.repoid, commit.commitid, report.code)

        return Response(
            CommitReportSerializer(report).data, status=status.HTTP_201_CREATED
        )


class ReportResultsSerializer(serializers.Serializer):
    report = CommitReportSerializer(read_only=True)
    external_id = serializers.UUIDField(read_only=True)
    state = serializers.ChoiceField(
        read_only=True, choices=ReportResults.ReportResultsStates.choices
    )
    result = serializers.JSONField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True)


class ReportResultsView(APIView, GetterMixin):
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
    ]

    def get(self, request, *args, **kwargs):
        repository = self.get_repo()
        commit = self.get_commit(repository)
        report = self.get_report(commit)
        try:
            report_results = ReportResults.objects.get(report=report)
        except ReportResults.DoesNotExist:
            log.info(
                "Report Results not found",
                extra=dict(
                    commit_sha=commit.commitid,
                    report_code=self.kwargs.get("report_code"),
                ),
            )
            return Response(
                data=["Report Results not found"], status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            ReportResultsSerializer(report_results).data, status=status.HTTP_200_OK
        )

    def post(self, request, *args, **kwargs):
        repository = self.get_repo()
        commit = self.get_commit(repository)
        report = self.get_report(commit)

        report_results, _created = ReportResults.objects.update_or_create(
            report=report,
            defaults={"state": ReportResults.ReportResultsStates.PENDING},
        )

        TaskService().create_report_results(
            commitid=commit.commitid,
            repoid=repository.repoid,
            report_code=report.code,
        )
        return Response(
            data=ReportResultsSerializer(report_results).data,
            status=status.HTTP_201_CREATED,
        )
